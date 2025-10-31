import os, uuid, subprocess
from dataclasses import dataclass
from typing import Dict, List
from werkzeug.utils import secure_filename

@dataclass
class RotateResult:
    output_path: str
    diagnostics: Dict

class VideoRotateService:
    ALLOWED = {"mp4","mov","mkv","webm","m4v"}

    @staticmethod
    def allowed(name: str) -> bool:
        return "." in name and name.rsplit(".",1)[1].lower() in VideoRotateService.ALLOWED

    @staticmethod
    def save_upload(fs, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(fs.filename or "")
        if not name: raise ValueError("Empty filename")
        if not VideoRotateService.allowed(name): raise ValueError("Unsupported video type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        fs.save(path)
        return path

    def __init__(self, video_path: str, work_root="uploads", output_root="rotate_output"):
        if not os.path.isfile(video_path): raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)
        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.output_path = os.path.join(self.output_root, f"{base}_rotated_{self.session_id}.mp4")

    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    def process(self, *, degrees: int = 90, metadata_only: bool = False,
                crf: int = 18, preset: str = "veryfast", copy_audio: bool = True) -> RotateResult:
        deg = int(degrees) % 360
        if deg not in (0, 90, 180, 270):
            raise ValueError("degrees must be one of 0, 90, 180, 270")

        if metadata_only:
            # Just tag rotation metadata (quick, no transcode). Some players ignore it.
            cmd = ["ffmpeg","-y","-i", self.video_path, "-c","copy","-metadata:s:v:0", f"rotate={deg}", self.output_path]
            self._run(cmd)
        else:
            # Re-encode with actual pixel rotation (universal).
            if deg == 0:
                vf = "null"
            elif deg == 90:
                vf = "transpose=1"  # clockwise
            elif deg == 180:
                vf = "hflip,vflip"
            else:  # 270 cw == 90 ccw
                vf = "transpose=2"

            cmd = ["ffmpeg","-y","-i", self.video_path, "-vf", vf,
                   "-c:v","libx264","-preset", preset,"-crf",str(int(crf)),
                   "-pix_fmt","yuv420p"]
            if copy_audio:
                cmd += ["-c:a","copy"]
            else:
                cmd += ["-c:a","aac","-b:a","192k"]
            cmd += [self.output_path]
            self._run(cmd)

        return RotateResult(
            output_path=self.output_path,
            diagnostics={"degrees": deg, "metadata_only": metadata_only, "crf": crf, "preset": preset, "copy_audio": copy_audio}
        )
