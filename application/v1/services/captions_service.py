import os, uuid, shutil, subprocess
from dataclasses import dataclass

from werkzeug.utils import secure_filename


@dataclass
class BurnResult:
    output_path: str
    diagnostics: dict


class CaptionsService:
    """
    Burn an .srt onto a video using ffmpeg 'subtitles' filter (libass).
    """

    @staticmethod
    def save_video(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        out = os.path.join(upload_dir, f"{os.path.splitext(name)[0]}_{uuid.uuid4().hex[:8]}{os.path.splitext(name)[1]}")
        file_storage.save(out)
        return out

    @staticmethod
    def save_srt(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "subs.srt")
        if not name.lower().endswith(".srt"):
            name = f"{name}.srt"
        out = os.path.join(upload_dir, f"{os.path.splitext(name)[0]}_{uuid.uuid4().hex[:8]}.srt")
        file_storage.save(out)
        return out

    def __init__(self, video_path: str, srt_path: str, output_root="captions_output"):
        if not os.path.isfile(video_path): raise FileNotFoundError(video_path)
        if not os.path.isfile(srt_path): raise FileNotFoundError(srt_path)
        self.video_path = video_path
        self.srt_path = srt_path
        base = os.path.splitext(os.path.basename(video_path))[0]
        self.out_root = output_root
        os.makedirs(self.out_root, exist_ok=True)
        self.output_path = os.path.join(self.out_root, f"{base}_subbed.mp4")

    def _run(self, cmd):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")

    def burn(self, fontsize=24, border=3) -> BurnResult:
        # You can customize ASS style via force_style
        style = f"Fontsize={fontsize},BorderStyle=3,OutlineColour=&H80000000,Outline={border}"
        vf = f"subtitles='{self.srt_path}':force_style='{style}'"
        self._run(["ffmpeg","-y","-i",self.video_path,"-vf",vf,"-c:a","copy", self.output_path])
        return BurnResult(output_path=self.output_path, diagnostics={"fontsize": fontsize, "border": border})
