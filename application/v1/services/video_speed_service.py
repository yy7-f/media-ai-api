import os, uuid, subprocess, math
from dataclasses import dataclass
from typing import Dict, List
from werkzeug.utils import secure_filename

@dataclass
class SpeedResult:
    output_path: str
    diagnostics: Dict

class VideoSpeedService:
    ALLOWED = {"mp4","mov","mkv","webm","m4v"}

    @staticmethod
    def allowed(name: str) -> bool:
        return "." in name and name.rsplit(".",1)[1].lower() in VideoSpeedService.ALLOWED

    @staticmethod
    def save_upload(fs, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(fs.filename or "")
        if not name: raise ValueError("Empty filename")
        if not VideoSpeedService.allowed(name): raise ValueError("Unsupported video type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        fs.save(path)
        return path

    def __init__(self, video_path: str, work_root="uploads", output_root="speed_output"):
        if not os.path.isfile(video_path): raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)
        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.output_path = os.path.join(self.output_root, f"{base}_speed_{self.session_id}.mp4")

    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    @staticmethod
    def _atempo_chain(factor: float) -> str:
        """
        atempo supports 0.5..2.0 per filter; chain to reach factor.
        Example: 4.0 -> atempo=2.0,atempo=2.0 ; 0.125 -> atempo=0.5,atempo=0.5,atempo=0.5
        """
        if factor <= 0:
            raise ValueError("speed factor must be > 0")

        parts = []
        remaining = factor
        # Bring remaining into [0.5, 2.0] by multiplying/dividing by 2
        while remaining > 2.0 + 1e-9:
            parts.append("atempo=2.0")
            remaining /= 2.0
        while remaining < 0.5 - 1e-9:
            parts.append("atempo=0.5")
            remaining *= 2.0
        parts.append(f"atempo={remaining:.6f}")
        return ",".join(parts)

    def process(self, *, factor: float = 1.25, crf: int = 18, preset: str = "veryfast") -> SpeedResult:
        if factor <= 0:
            raise ValueError("factor must be > 0")

        # Video timing: faster -> PTS/FACTOR ; slower -> PTS/FACTOR as well (since factor<1 increases PTS)
        setpts = f"setpts={1.0/float(factor):.6f}*PTS"
        atempo = self._atempo_chain(float(factor))

        cmd = ["ffmpeg","-y","-i", self.video_path]

        # Always re-encode video when speed != 1 (filters applied)
        if abs(factor - 1.0) < 1e-9:
            # No change → copy streams
            cmd += ["-c","copy", self.output_path]
        else:
            cmd += [
                "-vf", setpts,
                "-af", atempo,
                "-c:v","libx264","-preset", preset,"-crf", str(int(crf)),
                "-pix_fmt","yuv420p",
                "-c:a","aac","-b:a","192k",
                self.output_path
            ]

        self._run(cmd)
        return SpeedResult(
            output_path=self.output_path,
            diagnostics={"factor": factor, "crf": crf, "preset": preset}
        )
