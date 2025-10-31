import os, uuid, json, shutil, subprocess
from dataclasses import dataclass
from typing import List, Dict, Optional

from werkzeug.utils import secure_filename


@dataclass
class TranscriptionResult:
    transcript_json_path: str
    srt_path: str
    vtt_path: str
    diagnostics: Dict


class TranscriptionService:
    """
    Extract audio -> call ASR backend (hosted or local) -> write JSON, SRT, VTT.
    Default implementation expects a callable backend that returns segments:
      [{"start": 0.00, "end": 2.34, "text": "Hello world"}, ...]
    """

    ALLOWED_VIDEO = {"mp4", "mov", "mkv", "avi", "webm", "m4v", "mp3", "wav", "m4a", "aac", "flac"}

    @staticmethod
    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in TranscriptionService.ALLOWED_VIDEO

    @staticmethod
    def save_upload(file_storage, upload_dir: str = "uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(file_storage.filename or "")
        if not filename:
            raise ValueError("Empty filename")
        if not TranscriptionService.allowed_file(filename):
            raise ValueError("Unsupported file type")
        stem, ext = os.path.splitext(filename)
        unique_name = f"{stem}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(upload_dir, unique_name)
        file_storage.save(save_path)
        return save_path

    def __init__(self, input_path: str, work_root="uploads", output_root="transcribe_output"):
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"Input not found: {input_path}")
        self.input_path = input_path
        self.work_root = work_root
        self.output_root = output_root

        base = os.path.splitext(os.path.basename(self.input_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.session_dir = os.path.join(self.work_root, f"{base}_{self.session_id}")
        os.makedirs(self.session_dir, exist_ok=True)
        self.audio_wav = os.path.join(self.session_dir, f"{base}_16k.wav")

        self.out_root = os.path.join(self.output_root, f"{base}_{self.session_id}")
        os.makedirs(self.out_root, exist_ok=True)
        self.json_path = os.path.join(self.out_root, f"{base}.json")
        self.srt_path = os.path.join(self.out_root, f"{base}.srt")
        self.vtt_path = os.path.join(self.out_root, f"{base}.vtt")

    def _run(self, cmd: List[str]) -> None:
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")

    def extract_audio_16k_mono(self):
        self._run([
            "ffmpeg", "-y", "-i", self.input_path, "-vn",
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            self.audio_wav
        ])

    @staticmethod
    def _format_ts(ts: float) -> str:
        # HH:MM:SS,ms for SRT
        ms = int(round(ts * 1000))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, ms = divmod(rem, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    @staticmethod
    def _format_ts_vtt(ts: float) -> str:
        # HH:MM:SS.mmm for VTT
        ms = int(round(ts * 1000))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, ms = divmod(rem, 1000)
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"

    def _write_srt(self, segments: List[Dict]):
        with open(self.srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, start=1):
                f.write(f"{i}\n")
                f.write(f"{self._format_ts(seg['start'])} --> {self._format_ts(seg['end'])}\n")
                f.write(seg["text"].strip() + "\n\n")

    def _write_vtt(self, segments: List[Dict]):
        with open(self.vtt_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for seg in segments:
                f.write(f"{self._format_ts_vtt(seg['start'])} --> {self._format_ts_vtt(seg['end'])}\n")
                f.write(seg["text"].strip() + "\n\n")

    def process(self, asr_backend_callable, lang: Optional[str] = None) -> TranscriptionResult:
        """
        asr_backend_callable(audio_path:str, lang:str|None) -> List[segments]
        """
        self.extract_audio_16k_mono()
        segments = asr_backend_callable(self.audio_wav, lang)
        if not isinstance(segments, list) or not all({"start","end","text"} <= set(s.keys()) for s in segments):
            raise RuntimeError("ASR backend returned invalid segments format")

        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump({"segments": segments, "language": lang}, f, ensure_ascii=False, indent=2)

        self._write_srt(segments)
        self._write_vtt(segments)

        return TranscriptionResult(
            transcript_json_path=self.json_path,
            srt_path=self.srt_path,
            vtt_path=self.vtt_path,
            diagnostics={"num_segments": len(segments)}
        )

    def cleanup(self):
        try:
            shutil.rmtree(self.session_dir, ignore_errors=True)
        except Exception:
            pass
