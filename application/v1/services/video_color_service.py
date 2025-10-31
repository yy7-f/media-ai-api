import os, uuid, subprocess, shutil
from dataclasses import dataclass
from typing import Dict, List, Optional
from werkzeug.utils import secure_filename


@dataclass
class ColorResult:
    output_path: str
    diagnostics: Dict


class VideoColorService:
    ALLOWED = {"mp4", "mov", "mkv", "webm", "m4v"}

    @staticmethod
    def allowed_file(name: str) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in VideoColorService.ALLOWED

    @staticmethod
    def save_upload(fs, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(fs.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not VideoColorService.allowed_file(name):
            raise ValueError("Unsupported video type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        fs.save(path)
        return path

    def __init__(self, video_path: str, work_root="uploads", output_root="color_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.output_path = os.path.join(self.output_root, f"{base}_color_{self.session_id}.mp4")

    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    # Build FFmpeg color filter chain
    def _build_filter(self, mode: str, value: Optional[float] = None, lut_path: Optional[str] = None) -> str:
        mode = (mode or "cinematic").lower()

        if mode == "grayscale":
            return "hue=s=0"
        elif mode == "sepia":
            return "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"
        elif mode == "bw_highcontrast":
            return "hue=s=0,eq=contrast=1.5:brightness=0.05"
        elif mode == "cinematic":
            # subtle film tone (cool shadows, warm highlights)
            return "curves=preset=medium_contrast,eq=contrast=1.15:saturation=1.05,curves=blue='0/0 0.45/0.43 1/0.9'"
        elif mode == "brightness":
            val = value or 0.1
            return f"eq=brightness={val}"
        elif mode == "contrast":
            val = value or 1.2
            return f"eq=contrast={val}"
        elif mode == "saturation":
            val = value or 1.2
            return f"eq=saturation={val}"
        elif mode == "lut":
            if not lut_path or not os.path.isfile(lut_path):
                raise ValueError("Missing or invalid LUT file path")
            return f"lut3d=file='{lut_path}'"
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def process(self,
                *,
                mode: str = "cinematic",
                value: Optional[float] = None,
                lut_path: Optional[str] = None,
                crf: int = 18,
                preset: str = "veryfast",
                copy_audio: bool = True
                ) -> ColorResult:

        vf = self._build_filter(mode, value, lut_path)

        cmd = [
            "ffmpeg", "-y", "-i", self.video_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-pix_fmt", "yuv420p"
        ]
        if copy_audio:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-an"]
        cmd += [self.output_path]

        self._run(cmd)

        return ColorResult(
            output_path=self.output_path,
            diagnostics={
                "mode": mode,
                "value": value,
                "lut_path": lut_path,
                "filter": vf,
                "crf": crf,
                "preset": preset,
                "copy_audio": copy_audio
            }
        )

    def cleanup(self):
        try:
            shutil.rmtree(self.work_root, ignore_errors=True)
        except Exception:
            pass
