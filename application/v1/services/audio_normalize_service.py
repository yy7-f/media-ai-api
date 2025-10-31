import os, uuid, subprocess, json, shutil
from dataclasses import dataclass
from typing import Dict, List, Optional
from werkzeug.utils import secure_filename


@dataclass
class NormalizeResult:
    output_path: str
    diagnostics: Dict


class AudioNormalizeService:
    VIDEO_EXTS = {"mp4", "mov", "mkv", "webm", "m4v"}
    AUDIO_EXTS = {"mp3", "wav", "m4a", "aac", "flac", "ogg"}
    ALLOWED = VIDEO_EXTS | AUDIO_EXTS

    @staticmethod
    def allowed_file(name: str) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in AudioNormalizeService.ALLOWED

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not AudioNormalizeService.allowed_file(name):
            raise ValueError("Unsupported file type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, input_path: str, work_root="uploads", output_root="normalize_output"):
        if not os.path.isfile(input_path):
            raise FileNotFoundError(input_path)
        self.input_path = input_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        stem = os.path.splitext(os.path.basename(self.input_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.is_video = self.input_path.rsplit(".", 1)[1].lower() in self.VIDEO_EXTS

        # Output: video -> MP4, audio -> MP3 (default)
        if self.is_video:
            self.output_path = os.path.join(self.output_root, f"{stem}_norm_{self.session_id}.mp4")
        else:
            self.output_path = os.path.join(self.output_root, f"{stem}_norm_{self.session_id}.mp3")

    # ---------- helpers ----------
    def _run(self, cmd: List[str]) -> subprocess.CompletedProcess:
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")
        return p

    @staticmethod
    def _extract_loudnorm_json(txt: str) -> Dict:
        """
        FFmpeg loudnorm first pass prints a JSON block. We grab the first {...} block.
        """
        start = txt.find("{")
        end = txt.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError("Could not parse loudnorm measurement JSON")
        blob = txt[start : end + 1]
        return json.loads(blob)

    # ---------- main ----------
    def process(
        self,
        *,
        target_i: float = -14.0,   # Integrated loudness (LUFS)
        target_tp: float = -1.5,   # True peak (dBTP)
        target_lra: float = 11.0,  # Loudness range (LRA)
        audio_output: Optional[str] = None,  # only for audio inputs: mp3|wav|m4a (defaults to mp3)
        aac_bitrate: str = "192k"  # for video outputs (AAC bitrate)
    ) -> NormalizeResult:

        # -------- Pass 1: measure --------
        # We send output to null; loudnorm prints measurements we need for pass 2.
        pass1 = self._run([
            "ffmpeg", "-y",
            "-i", self.input_path,
            "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:dual_mono=true:print_format=json",
            "-f", "null", "-"
        ])
        stats = self._extract_loudnorm_json(pass1.stderr or pass1.stdout)

        # Extract measured values
        measured_I   = stats.get("input_i")
        measured_TP  = stats.get("input_tp")
        measured_LRA = stats.get("input_lra")
        measured_thresh = stats.get("input_thresh")
        offset       = stats.get("target_offset")

        # Build pass-2 filter with measured_* params (true two-pass normalization)
        loudnorm2 = (
            f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
            f"measured_I={measured_I}:measured_TP={measured_TP}:"
            f"measured_LRA={measured_LRA}:measured_thresh={measured_thresh}:"
            f"offset={offset}:linear=true:print_format=summary"
        )

        # -------- Pass 2: render --------
        if self.is_video:
            # Keep video as-is, normalize audio to AAC
            cmd = [
                "ffmpeg","-y",
                "-i", self.input_path,
                "-c:v", "copy",
                "-af", loudnorm2,
                "-c:a", "aac", "-b:a", aac_bitrate,
                self.output_path
            ]
        else:
            fmt = (audio_output or "mp3").lower()
            if fmt == "wav":
                cmd = [
                    "ffmpeg","-y",
                    "-i", self.input_path,
                    "-af", loudnorm2,
                    "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2",
                    self.output_path[:-4] + ".wav"
                ]
                self.output_path = self.output_path[:-4] + ".wav"
            elif fmt in ("m4a", "aac"):
                # m4a container with AAC
                cmd = [
                    "ffmpeg","-y",
                    "-i", self.input_path,
                    "-af", loudnorm2,
                    "-c:a", "aac", "-b:a", aac_bitrate,
                    self.output_path[:-4] + ".m4a"
                ]
                self.output_path = self.output_path[:-4] + ".m4a"
            else:
                # default mp3
                cmd = [
                    "ffmpeg","-y",
                    "-i", self.input_path,
                    "-af", loudnorm2,
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    self.output_path
                ]

        self._run(cmd)

        return NormalizeResult(
            output_path=self.output_path,
            diagnostics={
                "target": {"I": target_i, "TP": target_tp, "LRA": target_lra},
                "measured": {
                    "I": measured_I, "TP": measured_TP,
                    "LRA": measured_LRA, "thresh": measured_thresh,
                    "offset": offset
                },
                "is_video": self.is_video
            }
        )
