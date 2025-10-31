import os, uuid, subprocess
from dataclasses import dataclass
from typing import Optional
from werkzeug.utils import secure_filename

@dataclass
class OverlayResult:
    output_path: str
    diagnostics: dict

class OverlayTextService:
    ALLOWED_VIDEO = {"mp4","mov","mkv","webm","m4v"}

    @staticmethod
    def save_upload(file_storage, upload_dir: str) -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        ext = name.rsplit(".",1)[1].lower() if "." in name else ""
        if ext not in OverlayTextService.ALLOWED_VIDEO:
            raise ValueError("Unsupported video type")
        stem = name.rsplit(".",1)[0]
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}.{ext}")
        file_storage.save(path)
        return path

    def __init__(self, video_path: str, work_root="uploads", output_root="overlay_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.output_path = os.path.join(self.output_root, f"{base}_overlay_{uuid.uuid4().hex[:8]}.mp4")

    def _run(self, cmd):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    def process(self,
                *,
                text: str,
                x: str = "(w-text_w)/2",
                y: str = "h-100",
                start: Optional[float] = None,
                end: Optional[float] = None,
                fontsize: int = 42,
                fontcolor: str = "white",
                box: int = 1,
                boxcolor: str = "black@0.5",
                boxborderw: int = 10,
                fontfile: Optional[str] = None):
        """
        Overlay a single text line (with timing).
        - x, y: FFmpeg expressions (strings). Defaults: centered bottom.
        - start/end: seconds; if provided, enable between(t, start, end).
        - fontfile: optional absolute path to a TTF/OTF file.
        """

        # Escape single quotes and colons for drawtext
        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")

        expr = []
        expr.append(f"text='{esc(text)}'")
        expr.append(f"x={x}")
        expr.append(f"y={y}")
        expr.append(f"fontsize={fontsize}")
        expr.append(f"fontcolor={fontcolor}")
        expr.append(f"box={box}")
        expr.append(f"boxcolor={boxcolor}")
        expr.append(f"boxborderw={boxborderw}")
        if fontfile:
            expr.append(f"fontfile='{esc(fontfile)}'")
        if start is not None and end is not None:
            expr.append(f"enable='between(t,{float(start)},{float(end)})'")

        vf = f"drawtext={':'.join(expr)}"

        cmd = [
            "ffmpeg", "-y",
            "-i", self.video_path,
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            self.output_path
        ]
        self._run(cmd)

        return OverlayResult(
            output_path=self.output_path,
            diagnostics={
                "text": text, "x": x, "y": y,
                "start": start, "end": end,
                "fontsize": fontsize, "fontcolor": fontcolor,
                "box": box, "boxcolor": boxcolor, "boxborderw": boxborderw,
                "fontfile": fontfile
            }
        )
