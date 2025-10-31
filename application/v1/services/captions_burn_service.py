import os, uuid, shutil, subprocess, tempfile
from dataclasses import dataclass
from typing import Optional
from werkzeug.utils import secure_filename


@dataclass
class BurnResult:
    output_path: str
    diagnostics: dict


class CaptionsBurnService:
    ALLOWED_VIDEO = {"mp4", "mov", "mkv", "webm", "m4v"}
    ALLOWED_SUBS  = {"srt", "vtt"}

    @staticmethod
    def _allowed(fname: str, exts: set) -> bool:
        return "." in fname and fname.rsplit(".", 1)[1].lower() in exts

    @staticmethod
    def save_upload(file_storage, upload_dir: str, allowed_exts: set) -> str:
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(file_storage.filename or "")
        if not filename:
            raise ValueError("Empty filename")
        if not CaptionsBurnService._allowed(filename, allowed_exts):
            raise ValueError(f"Unsupported file type. Allowed: {', '.join(sorted(allowed_exts))}")
        stem, ext = os.path.splitext(filename)
        out = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(out)
        return out

    def __init__(self, video_path: str, subs_path: str, work_root="uploads", output_root="overlay_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")
        if not os.path.isfile(subs_path):
            raise FileNotFoundError(f"Subtitles not found: {subs_path}")

        self.video_path = video_path
        self.subs_path  = subs_path
        self.work_root  = work_root
        self.output_root= output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(self.video_path))[0]
        self.output_path = os.path.join(self.output_root, f"{base}_burned_{uuid.uuid4().hex[:8]}.mp4")

    def _run(self, cmd):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    @staticmethod
    def _vtt_to_srt(vtt_path: str, srt_path: str):
        # Very small conversion for WEBVTT → SRT (good enough for standard files)
        with open(vtt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out = []
        idx = 1
        for ln in lines:
            if ln.strip().upper() == "WEBVTT":
                continue
            if "-->" in ln:
                ts = ln.strip().replace(".", ",")  # 00:00:01.000 → 00:00:01,000
                out.append(str(idx))
                out.append(ts)
                idx += 1
            elif ln.strip() == "":
                out.append("")  # keep blank line
            else:
                out.append(ln.rstrip("\n"))
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(out).strip() + "\n")

    def process(self,
                *,
                fontfile: Optional[str] = None,
                fontsize: int = 28,
                primary_hex: str = "FFFFFF",
                outline_hex: str = "000000",
                outline: int = 2,
                y_margin: int = 24):
        """
        Burn subtitles using FFmpeg libass.
        - If VTT is provided, convert to SRT first for consistent styling.
        - Styling via force_style.
        """
        ext = self.subs_path.rsplit(".", 1)[1].lower()

        # Convert VTT → SRT if needed (FFmpeg subtitles filter is most consistent with SRT)
        subs_for_ffmpeg = self.subs_path
        tmp_srt = None
        if ext == "vtt":
            tmp_dir = tempfile.mkdtemp(prefix="vtt2srt_")
            tmp_srt = os.path.join(tmp_dir, "converted.srt")
            self._vtt_to_srt(self.subs_path, tmp_srt)
            subs_for_ffmpeg = tmp_srt

        # ASS hex format is BGR with &H..& (libass), but FFmpeg force_style takes standard hex in many builds.
        # We'll keep it simple: set PrimaryColour/OutlineColour using libass notation.
        # PrimaryColour & OutlineColour expect &HAABBGGRR (we'll use opaque AA=00)
        def ass_hex(rgb_hex):
            # Convert RRGGBB → &H00BBGGRR&
            rr = rgb_hex[0:2]; gg = rgb_hex[2:4]; bb = rgb_hex[4:6]
            return f"&H00{bb}{gg}{rr}&"

        style = (
            f"Fontsize={fontsize},"
            f"PrimaryColour={ass_hex(primary_hex)},"
            f"OutlineColour={ass_hex(outline_hex)},"
            f"BorderStyle=3,Outline={outline},Shadow=0,"
            f"MarginV={y_margin}"
        )

        # Build subtitles filter
        # Escape path for ffmpeg filter (space/colon)
        def esc(path: str) -> str:
            return path.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")

        vf = f"subtitles='{esc(subs_for_ffmpeg)}':force_style='{style}'"
        cmd = [
            "ffmpeg", "-y",
            "-i", self.video_path,
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            self.output_path
        ]
        if fontfile:
            # libass uses the system fontconfig; a direct fontfile in force_style isn't standard.
            # If you must force a font, pre-convert SRT→ASS with a template; omitted for simplicity.
            pass

        self._run(cmd)

        if tmp_srt:
            try: shutil.rmtree(os.path.dirname(tmp_srt), ignore_errors=True)
            except Exception: pass

        return BurnResult(
            output_path=self.output_path,
            diagnostics={
                "fontsize": fontsize,
                "primary_hex": primary_hex,
                "outline_hex": outline_hex,
                "outline": outline,
                "y_margin": y_margin
            }
        )
