import os, uuid, shutil, subprocess, json
from dataclasses import dataclass
from typing import List, Tuple
import cv2
import numpy as np
import easyocr
from werkzeug.utils import secure_filename


@dataclass
class VideoInpaintResult:
    output_path: str
    diagnostics: dict


class InpaintVideoService:
    ALLOWED = {"mp4", "mov", "mkv", "webm"}

    @staticmethod
    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in InpaintVideoService.ALLOWED

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not InpaintVideoService.allowed_file(name):
            raise ValueError("Unsupported file type (mp4/mov/mkv/webm)")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, video_path: str, work_root="uploads", output_root="inpaint_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.session_dir = os.path.join(work_root, f"{base}_{self.session_id}")
        self.frames_dir = os.path.join(self.session_dir, "frames")
        self.masks_dir = os.path.join(self.session_dir, "masks")
        self.inpainted_dir = os.path.join(self.session_dir, "inpainted")
        for d in (self.frames_dir, self.masks_dir, self.inpainted_dir):
            os.makedirs(d, exist_ok=True)

        os.makedirs(output_root, exist_ok=True)
        self.output_path = os.path.join(output_root, f"{base}_inpaint_{self.session_id}.mp4")
        self.meta_path = os.path.join(self.session_dir, "meta.json")

    # ---------- helpers ----------
    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")
        return p.stdout.strip()

    def _probe_fps(self) -> float:
        out = self._run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", self.video_path
        ])
        # r_frame_rate like "30000/1001" or "30/1"
        num, den = out.split("/")
        return float(num) / float(den)

    def _extract_frames(self):
        self._run(["ffmpeg", "-y", "-i", self.video_path, f"{self.frames_dir}/frame_%06d.png"])

    @staticmethod
    def _expand_box(bbox: List[Tuple[int, int]], W: int, H: int, pad: int = 8) -> Tuple[Tuple[int,int], Tuple[int,int]]:
        # bbox from EasyOCR: 4 points clockwise; we use min/max + padding
        xs = [int(p[0]) for p in bbox]
        ys = [int(p[1]) for p in bbox]
        x1, y1 = max(0, min(xs) - pad), max(0, min(ys) - pad)
        x2, y2 = min(W - 1, max(xs) + pad), min(H - 1, max(ys) + pad)
        return (x1, y1), (x2, y2)

    def _generate_masks(self, ocr_langs: str = "en", bbox_pad: int = 8, smooth: int = 1, static_thresh: float = 0.25):
        """
        Build per-frame masks + a static watermark mask (heatmap).
        smooth: number of neighboring frames to union (1 => t-1,t,t+1)
        static_thresh: fraction of frames a pixel must be 'on' to count as static logo
        """
        files = sorted(os.listdir(self.frames_dir))
        if not files:
            raise RuntimeError("No frames extracted")

        # read first frame for shape
        sample = cv2.imread(os.path.join(self.frames_dir, files[0]), cv2.IMREAD_COLOR)
        H, W = sample.shape[:2]
        reader = easyocr.Reader(ocr_langs.split(","))

        # heatmap accumulation for static logos
        heat = np.zeros((H, W), dtype=np.float32)
        frame_masks = []

        for fname in files:
            img = cv2.imread(os.path.join(self.frames_dir, fname))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            mask = np.zeros((H, W), dtype=np.uint8)

            results = reader.readtext(img)  # faster if you pass numpy
            for (bbox, _, _) in results:
                (x1, y1), (x2, y2) = self._expand_box(bbox, W, H, pad=bbox_pad)
                cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)

            # optional: also include very bright/dark spots (cheap heuristic)
            _, white_mask = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)
            _, black_mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)
            mask = cv2.bitwise_or(mask, white_mask)
            mask = cv2.bitwise_or(mask, black_mask)

            frame_masks.append(mask)
            heat += (mask > 0).astype(np.float32)

        # static watermark from heatmap
        heat /= len(files)
        static_mask = (heat >= static_thresh).astype(np.uint8) * 255
        if static_mask.any():
            k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            static_mask = cv2.dilate(static_mask, k, 1)

        # temporal smoothing (neighbor union)
        N = len(frame_masks)
        smoothed = []
        for i in range(N):
            m = frame_masks[i].copy()
            for d in range(1, smooth + 1):
                if i - d >= 0:
                    m = cv2.bitwise_or(m, frame_masks[i - d])
                if i + d < N:
                    m = cv2.bitwise_or(m, frame_masks[i + d])
            # union with static watermark
            m = cv2.bitwise_or(m, static_mask)
            smoothed.append(m)

        # write masks
        for i, fname in enumerate(files, start=1):
            out = os.path.join(self.masks_dir, f"frame_{i:06d}.png")
            cv2.imwrite(out, smoothed[i - 1])

        # save meta
        meta = {
            "num_frames": len(files),
            "shape": [W, H],
            "staticpct": float(static_mask.mean()) if static_mask.size else 0.0
        }
        with open(self.meta_path, "w") as f:
            json.dump(meta, f)

    def _run_lama_batch(self, device: str = "cpu"):
        # iopaint can take folders for image/mask and write to a folder
        self._run([
            "iopaint", "run",
            "--model", "lama",
            "--device", device,
            "--image", self.frames_dir,
            "--mask", self.masks_dir,
            "--output", self.inpainted_dir
        ])

    def _reassemble(self, fps: float):
        # Guard: ensure output frames exist; iopaint keeps filenames
        self._run([
            "ffmpeg", "-y",
            "-framerate", f"{fps:.6f}",
            "-i", f"{self.inpainted_dir}/frame_%06d.png",
            "-i", self.video_path,
            "-map", "0:v:0", "-map", "1:a?:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-shortest",
            self.output_path
        ])

    # ---------- public ----------
    def process(self, *, ocr_langs="en", bbox_pad=8, device="cpu", smooth=1, static_thresh=0.25, progress_cb=None):
        # phase 1: probe + extract
        if progress_cb: progress_cb(5, phase="probe")
        fps = self._probe_fps()
        if progress_cb: progress_cb(10, phase="extract")
        self._extract_frames()

        # phase 2: masks
        if progress_cb: progress_cb(40, phase="masks_start")
        self._generate_masks(ocr_langs=ocr_langs, bbox_pad=bbox_pad, smooth=smooth, static_thresh=static_thresh)
        if progress_cb: progress_cb(60, phase="masks_done")

        # phase 3: inpaint
        try:
            if progress_cb: progress_cb(65, phase="lama_start")
            self._run_lama_batch(device=device)
            if progress_cb: progress_cb(90, phase="lama_done")
        except Exception:
            # fallback OpenCV
            if progress_cb: progress_cb(80, phase="opencv_fallback")
            import cv2, os
            for fname in sorted(os.listdir(self.frames_dir)):
                src = os.path.join(self.frames_dir, fname)
                msk = os.path.join(self.masks_dir, fname)
                out = os.path.join(self.inpainted_dir, fname)
                im = cv2.imread(src)
                mk = cv2.imread(msk, cv2.IMREAD_GRAYSCALE)
                res = cv2.inpaint(im, mk, 3, cv2.INPAINT_TELEA)
                cv2.imwrite(out, res)
            if progress_cb: progress_cb(90, phase="opencv_done")

        # phase 4: reassemble
        if progress_cb: progress_cb(95, phase="reassemble")
        self._reassemble(fps=fps)

        if progress_cb: progress_cb(100, phase="done")
        return VideoInpaintResult(
            output_path=self.output_path,
            diagnostics={
                "device": device,
                "fps": fps,
                "bbox_pad": bbox_pad,
                "smooth": smooth,
                "static_thresh": static_thresh
            }
        )

    def cleanup(self):
        try:
            shutil.rmtree(self.session_dir, ignore_errors=True)
        except Exception:
            pass
