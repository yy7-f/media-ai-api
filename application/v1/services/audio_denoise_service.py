import os, uuid, subprocess, shutil
from dataclasses import dataclass
from typing import Dict, Optional
from werkzeug.utils import secure_filename


@dataclass
class AudioDenoiseResult:
    output_path: str
    diagnostics: Dict


class AudioDenoiseService:
    ALLOWED = {"mp3", "wav", "m4a", "flac", "ogg", "aac", "mp4", "mov", "mkv", "webm"}

    @staticmethod
    def allowed_file(name: str) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in AudioDenoiseService.ALLOWED

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not AudioDenoiseService.allowed_file(name):
            raise ValueError("Unsupported file type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, input_path: str, work_root="uploads", output_root="denoise_output"):
        if not os.path.isfile(input_path):
            raise FileNotFoundError(input_path)
        self.input_path = input_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(input_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.output_path = os.path.join(self.output_root, f"{base}_denoised_{self.session_id}.wav")

    def _run(self, cmd):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")
        return p

    def process(
        self,
        *,
        method: str = "afftdn",       # afftdn (FFT denoise) or arnndn (neural model)
        mode: str = "default",        # 'default' | 'music' | 'speech'
        out_format: str = "wav"       # output format
    ) -> AudioDenoiseResult:

        # Output format and path
        base = os.path.splitext(os.path.basename(self.input_path))[0]
        output_path = os.path.join(self.output_root, f"{base}_denoised_{self.session_id}.{out_format}")

        if method == "afftdn":
            # Simpler, CPU-only denoiser
            filter_str = f"afftdn=nt=w:{'m' if mode=='music' else 's'}"
        elif method == "arnndn":
            # Advanced neural denoiser (downloads model on first use)
            filter_str = "arnndn=m=rnnoise-models/speech" if mode == "speech" else "arnndn"
        else:
            raise ValueError("method must be 'afftdn' or 'arnndn'")

        cmd = [
            "ffmpeg", "-y", "-i", self.input_path,
            "-af", filter_str,
            "-c:v", "copy",  # keep video if exists
            "-c:a", "pcm_s16le" if out_format == "wav" else "aac",
            output_path
        ]
        self._run(cmd)

        return AudioDenoiseResult(
            output_path=output_path,
            diagnostics={
                "method": method,
                "mode": mode,
                "output_format": out_format
            }
        )

    def cleanup(self):
        try:
            shutil.rmtree(self.work_root, ignore_errors=True)
        except Exception:
            pass
