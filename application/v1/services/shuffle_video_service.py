import os
import uuid
import shutil
import subprocess
import random
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
from werkzeug.utils import secure_filename


@dataclass
class ShuffleResult:
    output_path: str
    diagnostics: dict


class ShuffleVideoService:
    ALLOWED = {"mp4", "mov", "mkv", "webm", "m4v"}

    @staticmethod
    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ShuffleVideoService.ALLOWED

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not ShuffleVideoService.allowed_file(name):
            raise ValueError("Unsupported file type (mp4/mov/mkv/webm/m4v)")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, video_path: str, work_root="uploads", output_root="shuffled_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.session_dir = os.path.join(work_root, f"{base}_{self.session_id}")
        self.parts_dir = os.path.join(self.session_dir, "parts")
        os.makedirs(self.parts_dir, exist_ok=True)
        os.makedirs(output_root, exist_ok=True)
        self.output_path = os.path.join(output_root, f"{base}_shuffled_{self.session_id}.mp4")

    # ---------- helpers ----------
    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")
        return p.stdout

    def _probe_duration(self) -> float:
        out = self._run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            self.video_path
        ])
        try:
            return float(out.strip())
        except Exception:
            return 0.0

    @staticmethod
    def _esc_ffmpeg_concat(path: str) -> str:
        # concat demuxer lines are single-quoted. Escape backslashes, colons, and single quotes.
        return path.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"'\''")

    def _write_concat(self, part_paths: List[str], concat_file: str, use_relative: bool = True) -> None:
        with open(concat_file, "w", encoding="utf-8") as f:
            for p in part_paths:
                if use_relative:
                    rel = os.path.relpath(p, start=self.session_dir)  # e.g. 'parts/part_0001.mp4'
                    f.write(f"file '{self._esc_ffmpeg_concat(rel)}'\n")
                else:
                    abspath = os.path.abspath(p)
                    f.write(f"file '{self._esc_ffmpeg_concat(abspath)}'\n")

    # ---------- core ----------
    def process(
        self,
        *,
        segments: Optional[List[Tuple[float, float]]] = None,
        chunk_sec: Optional[float] = None,
        seed: Optional[int] = None,
        reencode: bool = True,
        copy_audio: bool = True
    ) -> ShuffleResult:
        """
        - segments: explicit list of (start, end) seconds to keep, in any order.
        - OR chunk_sec: auto-split the whole video into equal chunks and shuffle them.
        - seed: deterministic shuffle seed (optional).
        - reencode: re-encode segments (safer joins). If False, tries -c copy (may glitch at non-keyframes).
        - copy_audio: if reencode=True, audio will be AAC; if False and c=copy, audio is copied.
        """

        if not segments and not chunk_sec:
            chunk_sec = 3  # default if not provided

        duration = self._probe_duration()
        if duration <= 0:
            raise RuntimeError("Could not probe video duration")

        # Build segments if chunk_sec is given
        if chunk_sec:
            chunk_sec = float(chunk_sec)
            if chunk_sec <= 0:
                raise ValueError("chunk_sec must be > 0")
            n = int(math.ceil(duration / chunk_sec))
            segments = []
            for i in range(n):
                s = i * chunk_sec
                e = min(duration, (i + 1) * chunk_sec)
                if e > s:
                    segments.append((s, e))

        # Validate / clamp
        cleaned: List[Tuple[float, float]] = []
        for (s, e) in segments or []:
            s = max(0.0, float(s))
            e = max(0.0, float(e))
            if e <= s:
                continue
            if s >= duration:
                continue
            e = min(e, duration)
            cleaned.append((s, e))
        if not cleaned:
            raise ValueError("No valid segments after validation")

        # Shuffle
        if seed is not None:
            random.seed(int(seed))
        random.shuffle(cleaned)

        # Extract parts
        part_paths: List[str] = []
        for idx, (s, e) in enumerate(cleaned, start=1):
            part = os.path.join(self.parts_dir, f"part_{idx:04d}.mp4")
            if reencode:
                # Accurate cuts with re-encode
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{s:.3f}", "-to", f"{e:.3f}",
                    "-i", self.video_path,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    part
                ]
            else:
                # Fast but only safe on keyframes (may glitch otherwise)
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{s:.3f}", "-to", f"{e:.3f}",
                    "-i", self.video_path,
                    "-c", "copy",
                    part
                ]
            self._run(cmd)
            part_paths.append(part)

        # Ensure parts exist
        missing = [p for p in part_paths if not os.path.exists(p)]
        if missing:
            raise RuntimeError(f"Missing parts after extraction: {missing[:3]}{'...' if len(missing) > 3 else ''}")

        # Concat parts (relative paths)
        concat_file = os.path.join(self.session_dir, "concat.txt")
        self._write_concat(part_paths, concat_file, use_relative=True)

        # Final join
        if reencode:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k" if copy_audio else "128k",
                self.output_path
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c", "copy",
                self.output_path
            ]
        self._run(cmd)

        return ShuffleResult(
            output_path=self.output_path,
            diagnostics={
                "duration": duration,
                "num_segments": len(cleaned),
                "seed": seed,
                "reencode": reencode
            }
        )

    def cleanup(self):
        try:
            shutil.rmtree(self.session_dir, ignore_errors=True)
        except Exception:
            pass
