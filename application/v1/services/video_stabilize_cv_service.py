import os, uuid, math, shutil, subprocess
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
import cv2
from werkzeug.utils import secure_filename


@dataclass
class CVStabilizeResult:
    output_path: str
    diagnostics: Dict


class VideoStabilizeCVService:
    ALLOWED = {"mp4", "mov", "mkv", "webm", "m4v"}

    # ---------- uploads ----------
    @staticmethod
    def allowed_file(name: str) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in VideoStabilizeCVService.ALLOWED

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not VideoStabilizeCVService.allowed_file(name):
            raise ValueError("Unsupported video type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    # ---------- init ----------
    def __init__(self, video_path: str, work_root="uploads", output_root="stabilize_cv_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.session_dir = os.path.join(self.work_root, f"{base}_{self.session_id}")
        os.makedirs(self.session_dir, exist_ok=True)

        self.silent_out = os.path.join(self.session_dir, f"{base}_stabilized_silent_{self.session_id}.mp4")
        self.output_path = os.path.join(self.output_root, f"{base}_stabilized_{self.session_id}.mp4")

    # ---------- helpers ----------
    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")
        return p

    @staticmethod
    def _moving_average(data: np.ndarray, radius: int) -> np.ndarray:
        if radius <= 0:
            return data.copy()
        # reflect padding for nice edges
        pad = max(1, radius)
        padded = np.pad(data, ((pad, pad), (0, 0)), mode="edge")
        kernel = np.ones((2 * pad + 1, 1)) / float(2 * pad + 1)
        smoothed = np.apply_along_axis(lambda m: np.convolve(m, kernel.ravel(), mode="valid"), 0, padded)
        return smoothed

    @staticmethod
    def _build_transform(dx: float, dy: float, da: float, zoom: float, cx: float, cy: float) -> np.ndarray:
        """
        2x3 affine: rotate by da, translate by dx,dy, and optional isotropic zoom around center (cx,cy).
        """
        cos, sin = math.cos(da), math.sin(da)
        a = zoom * cos
        b = zoom * sin
        # rotate+scale around origin, then translate; adjust to keep center as pivot
        # T = RZ + translation + pivot compensation
        # newX = a*x - b*y + tx
        # newY = b*x + a*y + ty
        tx = dx + (1 - a) * cx + b * cy
        ty = dy + (1 - a) * cy - b * cx
        return np.array([[a, -b, tx],
                         [b,  a, ty]], dtype=np.float32)

    # ---------- main ----------
    def process(
        self,
        *,
        smoothing_radius: int = 30,         # moving-average radius in frames
        max_corners: int = 400,             # feature count
        quality_level: float = 0.01,        # feature quality
        min_distance: int = 30,             # feature min distance
        ransac_reproj_thresh: float = 3.0,  # robust affine estimation
        border_mode: str = "black",         # black | reflect | replicate
        zoom_percent: float = 5.0,          # auto crop/zoom to hide borders
        keep_audio: bool = True,            # mux original audio back with ffmpeg
        crf: int = 18,
        preset: str = "veryfast"
    ) -> CVStabilizeResult:

        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError("OpenCV could not open video")

        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Read first frame
        ok, prev = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError("Failed to read first frame")
        prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

        # ORB/KLT: we’ll use goodFeaturesToTrack + LK optical flow
        transforms: List[Tuple[float, float, float]] = []  # dx, dy, da

        # Optical flow params
        lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )

        for _ in range(n_frames - 1):
            ok, curr = cap.read()
            if not ok:
                break
            curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)

            prev_pts = cv2.goodFeaturesToTrack(
                prev_gray,
                maxCorners=max_corners,
                qualityLevel=quality_level,
                minDistance=min_distance,
                blockSize=3
            )
            if prev_pts is None or len(prev_pts) < 8:
                # Not enough features; assume no motion
                transforms.append((0.0, 0.0, 0.0))
                prev_gray = curr_gray
                continue

            curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None, **lk_params)
            # Filter valid points
            idx = status.ravel() == 1
            prev_pts_valid = prev_pts[idx]
            curr_pts_valid = curr_pts[idx] if curr_pts is not None else None

            if curr_pts_valid is None or len(curr_pts_valid) < 8:
                transforms.append((0.0, 0.0, 0.0))
                prev_gray = curr_gray
                continue

            # Estimate partial affine (translation + rotation + scale)
            M, inliers = cv2.estimateAffinePartial2D(prev_pts_valid, curr_pts_valid, method=cv2.RANSAC,
                                                     ransacReprojThreshold=ransac_reproj_thresh)
            if M is None:
                transforms.append((0.0, 0.0, 0.0))
            else:
                dx = float(M[0, 2])
                dy = float(M[1, 2])
                da = math.atan2(M[1, 0], M[0, 0])  # rotation angle
                transforms.append((dx, dy, da))

            prev_gray = curr_gray

        cap.release()

        if not transforms:
            raise RuntimeError("Could not estimate motion (no transforms)")

        # Build cumulative trajectory
        trajectory = np.cumsum(np.array(transforms), axis=0)  # shape (N, 3)

        # Smooth it
        smooth_traj = self._moving_average(trajectory, smoothing_radius)

        # Delta to apply: transforms + (smooth - traj)
        diff = smooth_traj - trajectory
        new_transforms = np.array(transforms) + diff

        # Prepare writer: we write to a temporary silent mp4, then mux audio
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # widely compatible
        writer = cv2.VideoWriter(self.silent_out, fourcc, fps, (w, h))
        if not writer.isOpened():
            raise RuntimeError("VideoWriter failed to open")

        # Border handling
        border_map = {
            "black": cv2.BORDER_CONSTANT,
            "reflect": cv2.BORDER_REFLECT,
            "replicate": cv2.BORDER_REPLICATE
        }
        border_flag = border_map.get(border_mode.lower(), cv2.BORDER_CONSTANT)
        zoom = max(1.0, 1.0 + float(zoom_percent) / 100.0)

        # Second pass: apply transforms
        cap = cv2.VideoCapture(self.video_path)
        ok, frame = cap.read()
        writer.write(frame)  # write the first frame as-is
        prev = frame
        i = 0

        cx, cy = w / 2.0, h / 2.0

        while True:
            ok, frame = cap.read()
            if not ok or i >= len(new_transforms):
                break

            dx, dy, da = new_transforms[i]
            M = self._build_transform(dx, dy, da, zoom, cx, cy)

            stabilized = cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=border_flag)

            writer.write(stabilized)
            i += 1

        cap.release()
        writer.release()

        # Final: mux original audio back (if requested). If the input had no audio, copy will just warn and continue.
        if keep_audio:
            self._run([
                "ffmpeg", "-y",
                "-i", self.silent_out, "-i", self.video_path,
                "-map", "0:v:0", "-map", "1:a:0?",
                "-c:v", "libx264", "-preset", preset, "-crf", str(int(crf)),
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                self.output_path
            ])
        else:
            # Re-encode the silent mp4 to ensure consistent x264 params output_root
            self._run([
                "ffmpeg", "-y",
                "-i", self.silent_out,
                "-c:v", "libx264", "-preset", preset, "-crf", str(int(crf)),
                "-pix_fmt", "yuv420p",
                self.output_path
            ])

        return CVStabilizeResult(
            output_path=self.output_path,
            diagnostics={
                "frames_used": len(transforms) + 1,
                "fps": fps,
                "size": [w, h],
                "smoothing_radius": smoothing_radius,
                "zoom_percent": zoom_percent,
                "border_mode": border_mode,
                "keep_audio": keep_audio,
                "crf": crf,
                "preset": preset
            }
        )

    def cleanup(self):
        try:
            shutil.rmtree(self.session_dir, ignore_errors=True)
        except Exception:
            pass
