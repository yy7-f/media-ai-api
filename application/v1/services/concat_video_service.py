import os, uuid, subprocess, shutil
from dataclasses import dataclass
from typing import List
from werkzeug.utils import secure_filename

@dataclass
class ConcatResult:
    output_path: str
    diagnostics: dict

class ConcatVideoService:
    ALLOWED = {"mp4","mov","mkv","webm","m4v"}

    @staticmethod
    def allowed_file(name: str) -> bool:
        return "." in name and name.rsplit(".",1)[1].lower() in ConcatVideoService.ALLOWED

    @staticmethod
    def save_uploads(file_storages: List, upload_dir="uploads") -> List[str]:
        os.makedirs(upload_dir, exist_ok=True)
        saved = []
        for fs in file_storages:
            name = secure_filename(fs.filename or "")
            if not name:
                raise ValueError("Empty filename")
            if not ConcatVideoService.allowed_file(name):
                raise ValueError(f"Unsupported type: {name}")
            stem, ext = os.path.splitext(name)
            path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
            fs.save(path)
            saved.append(path)
        return saved

    def __init__(self, input_paths: List[str], work_root="uploads", output_root="concat_output"):
        if not input_paths:
            raise ValueError("No input videos")
        for p in input_paths:
            if not os.path.isfile(p):
                raise FileNotFoundError(p)
        self.input_paths = input_paths
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(input_paths[0]))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.session_dir = os.path.join(self.work_root, f"{base}_{self.session_id}")
        os.makedirs(self.session_dir, exist_ok=True)

        self.concat_list = os.path.join(self.session_dir, "concat.txt")
        self.output_path = os.path.join(self.output_root, f"{base}_concat_{self.session_id}.mp4")

    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    @staticmethod
    def _esc(path: str) -> str:
        return path.replace("\\","\\\\").replace(":", r"\:").replace("'", r"'\''")

    def _write_concat_list(self, reencode: bool):
        # For reencode: we can safely mix different codecs/resolutions
        # For copy: inputs must share identical codec/params (fast path)
        with open(self.concat_list, "w", encoding="utf-8") as f:
            for p in self.input_paths:
                # concat *demuxer* requires the "file '...'" syntax
                f.write(f"file '{self._esc(os.path.abspath(p))}'\n")

    def process(self, *, reencode: bool = True, audio_bitrate="192k", crf="18", preset="veryfast") -> ConcatResult:
        self._write_concat_list(reencode=reencode)

        if reencode:
            cmd = [
                "ffmpeg","-y",
                "-f","concat","-safe","0","-i", self.concat_list,
                "-c:v","libx264","-preset", preset, "-crf", str(crf),
                "-pix_fmt","yuv420p",
                "-c:a","aac","-b:a", audio_bitrate,
                self.output_path
            ]
        else:
            # Fast path, only if all inputs match exactly (codec/profile/size/fps)
            cmd = [
                "ffmpeg","-y",
                "-f","concat","-safe","0","-i", self.concat_list,
                "-c","copy",
                self.output_path
            ]
        self._run(cmd)

        return ConcatResult(
            output_path=self.output_path,
            diagnostics={
                "num_inputs": len(self.input_paths),
                "reencode": reencode,
                "audio_bitrate": audio_bitrate,
                "crf": crf,
                "preset": preset
            }
        )

    def cleanup(self):
        try:
            shutil.rmtree(self.session_dir, ignore_errors=True)
        except Exception:
            pass
