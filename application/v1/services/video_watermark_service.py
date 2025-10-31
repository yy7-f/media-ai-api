import os, uuid, subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional
from werkzeug.utils import secure_filename


@dataclass
class WatermarkResult:
    output_path: str
    diagnostics: Dict


class VideoWatermarkService:
    VIDEO_EXTS = {"mp4", "mov", "mkv", "webm", "m4v"}
    IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "bmp", "gif"}  # (gif/apng works; ffmpeg reads first stream)
    ALLOWED_VIDEO = VIDEO_EXTS
    ALLOWED_IMAGE = IMAGE_EXTS

    @staticmethod
    def _allowed(name: str, exts: set) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in exts

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads", allowed: set = None) -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if allowed and not VideoWatermarkService._allowed(name, allowed):
            raise ValueError(f"Unsupported file type: {name}")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, video_path: str, image_path: str, work_root="uploads", output_root="watermark_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        if not os.path.isfile(image_path):
            raise FileNotFoundError(image_path)

        self.video_path = video_path
        self.image_path = image_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.output_path = os.path.join(self.output_root, f"{base}_wm_{self.session_id}.mp4")

    # ------------- helpers -------------
    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    @staticmethod
    def _overlay_xy(preset: str, margin_x: int, margin_y: int) -> (str, str):
        """
        Returns expressions for overlay x,y using main_w/main_h and overlay_w/overlay_h.
        """
        p = (preset or "bottom-right").lower()
        if p == "top-left":
            x = f"{margin_x}"
            y = f"{margin_y}"
        elif p == "top-right":
            x = f"main_w - overlay_w - {margin_x}"
            y = f"{margin_y}"
        elif p == "bottom-left":
            x = f"{margin_x}"
            y = f"main_h - overlay_h - {margin_y}"
        elif p == "center":
            x = f"(main_w - overlay_w)/2"
            y = f"(main_h - overlay_h)/2"
        else:  # bottom-right (default)
            x = f"main_w - overlay_w - {margin_x}"
            y = f"main_h - overlay_h - {margin_y}"
        return x, y

    # ------------- main -------------
    def process(
        self,
        *,
        position: str = "bottom-right",     # top-left|top-right|bottom-left|bottom-right|center
        margin_x: int = 24,
        margin_y: int = 24,
        opacity: float = 0.85,              # 0..1, applied to watermark alpha
        scale_pct: float = 20.0,            # scale watermark relative to its ORIGINAL size (not the video)
        t_start: Optional[float] = None,    # seconds (show watermark starting at t_start)
        t_end: Optional[float] = None,      # seconds (hide after t_end). If None: show until end
        crf: int = 18,
        preset: str = "veryfast",
        copy_audio: bool = True
    ) -> WatermarkResult:
        """
        Notes:
          - Scaling is relative to watermark file (simple & fast). If you need
            scaling relative to the VIDEO size, we can switch to `scale2ref`.
          - GIF/APNG is supported; the first video stream of the image file is taken.
        """
        # Clamp inputs
        op = min(max(opacity, 0.0), 1.0)
        sp = max(1.0, float(scale_pct))  # avoid zero/negative

        # Build x/y expressions
        x_expr, y_expr = self._overlay_xy(position, int(margin_x), int(margin_y))

        # FilterComplex:
        #  1) Read watermark, ensure RGBA, set opacity with colorchannelmixer (aa=opacity)
        #  2) Scale watermark by scale_pct of its original size (keep AR)
        #  3) Overlay with optional enable=between(t, t_start, t_end)
        wm_chain = [
            "[1:v]format=rgba",
            f"colorchannelmixer=aa={op:.6f}",
            f"scale=trunc(iw*{sp/100.0}):trunc(ih*{sp/100.0}):flags=bicubic"
        ]
        wm_label = "[wm]"
        wm_chain_str = ",".join(wm_chain) + wm_label

        enable_expr = None
        if t_start is not None and t_end is not None:
            if t_end <= t_start:
                # if user inverted, just show from start to end-of-video
                enable_expr = f"enable='gte(t,{float(t_start):.3f})'"
            else:
                enable_expr = f"enable='between(t,{float(t_start):.3f},{float(t_end):.3f})'"
        elif t_start is not None:
            enable_expr = f"enable='gte(t,{float(t_start):.3f})'"

        overlay_args = f"x={x_expr}:y={y_expr}"
        if enable_expr:
            overlay_args += f":{enable_expr}"

        filter_complex = f"{wm_chain_str};[0:v]{wm_label}overlay={overlay_args}[vout]"

        cmd = [
            "ffmpeg", "-y",
            "-i", self.video_path,
            "-i", self.image_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
        ]
        if copy_audio:
            cmd += ["-map", "0:a?", "-c:a", "copy"]
        else:
            cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]

        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(int(crf)), "-pix_fmt", "yuv420p", self.output_path]

        self._run(cmd)

        return WatermarkResult(
            output_path=self.output_path,
            diagnostics={
                "position": position,
                "margin_x": margin_x,
                "margin_y": margin_y,
                "opacity": op,
                "scale_pct": sp,
                "t_start": t_start,
                "t_end": t_end,
                "crf": crf,
                "preset": preset,
                "copy_audio": copy_audio
            }
        )
