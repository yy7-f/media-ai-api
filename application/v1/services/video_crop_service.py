import os, uuid, subprocess, json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from werkzeug.utils import secure_filename

from application.utils.gcs_upload import upload_to_gcs


@dataclass
class CropResult:
    output_path: str
    diagnostics: Dict


class VideoCropService:
    ALLOWED = {"mp4", "mov", "mkv", "webm", "m4v"}

    @staticmethod
    def allowed(name: str) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in VideoCropService.ALLOWED

    @staticmethod
    def save_upload(fs, upload_dir: str = "/tmp/uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(fs.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not VideoCropService.allowed(name):
            raise ValueError("Unsupported video type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        fs.save(path)
        return path

    def __init__(self, video_path: str, work_root: str = "/tmp/uploads", output_root: str = "/tmp/crop_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.output_path = os.path.join(self.output_root, f"{base}_crop_{self.session_id}.mp4")

    # ---------- helpers ----------
    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")
        return p

    def _probe_size(self) -> Optional[Dict[str, int]]:
        p = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "json", self.video_path
            ],
            capture_output=True, text=True
        )
        if p.returncode != 0:
            return None
        info = json.loads(p.stdout or "{}")
        if not info.get("streams"):
            return None
        v = info["streams"][0]
        return {"w": int(v.get("width", 0)), "h": int(v.get("height", 0))}

    @staticmethod
    def _parse_aspect(aspect: str) -> Tuple[int, int]:
        s = aspect.strip().lower().replace("x", ":").replace("-", ":").replace(" ", "")
        if ":" not in s:
            raise ValueError("aspect must look like W:H (e.g., 9:16)")
        a, b = s.split(":", 1)
        aw, ah = int(a), int(b)
        if aw <= 0 or ah <= 0:
            raise ValueError("aspect parts must be positive integers")
        return aw, ah

    @staticmethod
    def _max_rect_for_aspect(src_w: int, src_h: int, aw: int, ah: int) -> Tuple[int, int]:
        """Largest width/height that fits the aspect inside the source."""
        target_ratio = aw / ah
        src_ratio = src_w / src_h
        if src_ratio > target_ratio:
            out_h = src_h
            out_w = int(round(out_h * target_ratio))
        else:
            out_w = src_w
            out_h = int(round(out_w / target_ratio))
        return out_w, out_h

    @staticmethod
    def _place_rect(src_w: int, src_h: int, rect_w: int, rect_h: int, mode: str) -> Tuple[int, int]:
        """Return (x,y) based on mode."""
        m = (mode or "center").lower()
        if m == "center":
            x = (src_w - rect_w) // 2
            y = (src_h - rect_h) // 2
        elif m == "top":
            x = (src_w - rect_w) // 2
            y = 0
        elif m == "bottom":
            x = (src_w - rect_w) // 2
            y = src_h - rect_h
        elif m == "left":
            x = 0
            y = (src_h - rect_h) // 2
        elif m == "right":
            x = src_w - rect_w
            y = (src_h - rect_h) // 2
        elif m == "top-left":
            x, y = 0, 0
        elif m == "top-right":
            x, y = src_w - rect_w, 0
        elif m == "bottom-left":
            x, y = 0, src_h - rect_h
        elif m == "bottom-right":
            x, y = src_w - rect_w, src_h - rect_h
        else:
            # fallback
            x = (src_w - rect_w) // 2
            y = (src_h - rect_h) // 2
        return x, y

    @staticmethod
    def _ensure_even_rect(x: int, y: int, w: int, h: int, src_w: int, src_h: int) -> Tuple[int, int, int, int]:
        if w % 2 == 1:
            w -= 1
        if h % 2 == 1:
            h -= 1
        if w < 2:
            w = 2
        if h < 2:
            h = 2
        if x % 2 == 1:
            x -= 1
        if y % 2 == 1:
            y -= 1
        x = max(0, min(x, src_w - w))
        y = max(0, min(y, src_h - h))
        return x, y, w, h

    # ---------- main ----------
    def process(
        self,
        *,
        # Manual rectangle (takes precedence if all four provided)
        x: Optional[int] = None,
        y: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        # Aspect preset + placement
        aspect: Optional[str] = None,   # e.g. "9:16"
        mode: str = "center",           # center|top|bottom|left|right|top-left|top-right|bottom-left|bottom-right
        offset_x: int = 0,              # nudge after placement
        offset_y: int = 0,
        ensure_even: bool = True,
        crf: int = 18,
        preset: str = "veryfast",
        copy_audio: bool = True,
        safe_bounds: bool = True,
        bucket_name: Optional[str] = None,  # 👈 GCS bucket (optional)
    ) -> CropResult:

        src = self._probe_size()
        if not src or src["w"] <= 0 or src["h"] <= 0:
            raise RuntimeError("Could not probe input video size")
        sw, sh = src["w"], src["h"]

        manual_ok = all(v is not None for v in (x, y, width, height))
        if manual_ok:
            X, Y, W, H = int(x), int(y), int(width), int(height)
            if W <= 0 or H <= 0 or X < 0 or Y < 0:
                raise ValueError("Invalid manual crop rectangle")
        elif aspect:
            aw, ah = self._parse_aspect(aspect)
            W, H = self._max_rect_for_aspect(sw, sh, aw, ah)
            X, Y = self._place_rect(sw, sh, W, H, mode)
            X += int(offset_x)
            Y += int(offset_y)
        else:
            raise ValueError("Provide either x,y,width,height OR aspect=9:16")

        if safe_bounds:
            W = min(W, sw)
            H = min(H, sh)
            X = min(max(0, X), max(0, sw - W))
            Y = min(max(0, Y), max(0, sh - H))

        if ensure_even:
            X, Y, W, H = self._ensure_even_rect(X, Y, W, H, sw, sh)

        crop_expr = f"crop={W}:{H}:{X}:{Y}"

        cmd = [
            "ffmpeg", "-y",
            "-i", self.video_path,
            "-vf", crop_expr,
            "-c:v", "libx264", "-preset", preset, "-crf", str(int(crf)),
            "-pix_fmt", "yuv420p",
        ]
        if copy_audio:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-an"]
        cmd += [self.output_path]

        self._run(cmd)

        gcs_url = None
        if bucket_name:
            dest_name = os.path.basename(self.output_path)
            gcs_path = f"crop/{dest_name}"
            gcs_url = upload_to_gcs(self.output_path, bucket_name, gcs_path)

        return CropResult(
            output_path=self.output_path,
            diagnostics={
                "source_size": src,
                "rect": {"x": X, "y": Y, "w": W, "h": H},
                "aspect": aspect,
                "mode": mode,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "ensure_even": ensure_even,
                "crf": crf,
                "preset": preset,
                "copy_audio": copy_audio,
                "safe_bounds": safe_bounds,
                "gcs_url": gcs_url,
            },
        )
