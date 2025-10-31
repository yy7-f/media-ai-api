import os, uuid, subprocess, json
from dataclasses import dataclass
from typing import Dict, List, Optional
from werkzeug.utils import secure_filename


@dataclass
class TrimResult:
    output_path: str
    diagnostics: Dict


class VideoTrimService:
    ALLOWED = {"mp4", "mov", "mkv", "webm", "m4v"}

    # ---------- uploads ----------
    @staticmethod
    def allowed(name: str) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in VideoTrimService.ALLOWED

    @staticmethod
    def save_upload(fs, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(fs.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not VideoTrimService.allowed(name):
            raise ValueError("Unsupported video type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        fs.save(path)
        return path

    # ---------- init ----------
    def __init__(self, video_path: str, work_root="uploads", output_root="trim_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.output_path = os.path.join(self.output_root, f"{base}_trim_{self.session_id}.mp4")

    # ---------- helpers ----------
    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")
        return p

    def _probe_duration(self) -> Optional[float]:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", self.video_path],
            capture_output=True, text=True
        )
        if p.returncode != 0:
            return None
        try:
            return float((p.stdout or "").strip())
        except Exception:
            return None

    # ---------- main ----------
    def process(
        self,
        *,
        start: Optional[float] = None,    # seconds
        end: Optional[float] = None,      # seconds
        duration: Optional[float] = None, # seconds (alternative to end)
        precise: bool = True,             # True=re-encode (frame-accurate), False=fast copy (keyframe)
        crf: int = 18,
        preset: str = "veryfast",
        copy_audio: bool = True
    ) -> TrimResult:

        if start is None and end is None and duration is None:
            raise ValueError("Provide start/end or start/duration or end/duration")

        # Normalize & validate times
        vid_dur = self._probe_duration() or 0.0
        s = max(0.0, float(start or 0.0))
        if duration is not None:
            t = max(0.0, float(duration))
        elif end is not None:
            e = max(0.0, float(end))
            if e <= s:
                raise ValueError("end must be greater than start")
            t = e - s
        else:
            # end only with no start: interpret as [0, end]
            t = max(0.0, float(end or 0.0)) - s

        if t <= 0:
            raise ValueError("Trim duration must be > 0")

        # Build ffmpeg command
        if precise:
            # Accurate: seek after input, re-encode (handles non-keyframe starts)
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{s:.6f}",
                "-i", self.video_path,
                "-t", f"{t:.6f}",
                "-c:v", "libx264", "-preset", preset, "-crf", str(int(crf)),
                "-pix_fmt", "yuv420p",
            ]
            if copy_audio:
                cmd += ["-c:a", "aac", "-b:a", "192k"]  # must re-encode since we filter video
            else:
                cmd += ["-an"]
            cmd += [self.output_path]
        else:
            # Fast: stream copy (exact only if start hits keyframe)
            # Use -ss BEFORE -i for fast seek + -to for end relative to start
            cmd = [
                "ffmpeg", "-y",
                "-ss", f"{s:.6f}",
                "-to", f"{s + t:.6f}",
                "-i", self.video_path,
                "-c", "copy",
                self.output_path
            ]

        self._run(cmd)

        return TrimResult(
            output_path=self.output_path,
            diagnostics={
                "start": s,
                "duration": t,
                "end": s + t,
                "precise": precise,
                "crf": crf,
                "preset": preset,
                "copy_audio": copy_audio,
                "video_duration_probe": vid_dur
            }
        )
