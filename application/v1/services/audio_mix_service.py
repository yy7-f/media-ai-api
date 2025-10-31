import os, uuid, subprocess, shutil
from dataclasses import dataclass
from typing import Dict, List, Optional
from werkzeug.utils import secure_filename


@dataclass
class MixResult:
    output_path: str
    diagnostics: Dict


class AudioMixService:
    VIDEO_EXTS = {"mp4","mov","mkv","webm","m4v"}
    AUDIO_EXTS = {"mp3","wav","m4a","aac","flac","ogg"}
    ALLOWED_MAIN = VIDEO_EXTS | AUDIO_EXTS
    ALLOWED_BGM  = AUDIO_EXTS  # BGM must be audio

    @staticmethod
    def _allowed(name: str, exts: set) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in exts

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads", allowed: set = None) -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if allowed and not AudioMixService._allowed(name, allowed):
            raise ValueError(f"Unsupported file type: {name}")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, main_path: str, bgm_path: str, work_root="uploads", output_root="mix_output"):
        if not os.path.isfile(main_path):
            raise FileNotFoundError(main_path)
        if not os.path.isfile(bgm_path):
            raise FileNotFoundError(bgm_path)

        self.main_path = main_path
        self.bgm_path  = bgm_path
        self.work_root = work_root
        self.output_root = output_root

        os.makedirs(self.output_root, exist_ok=True)
        base = os.path.splitext(os.path.basename(self.main_path))[0]
        self.session_id = uuid.uuid4().hex[:8]

        is_video = self.main_path.rsplit(".", 1)[1].lower() in self.VIDEO_EXTS
        out_ext = ".mp4" if is_video else ".mp3"
        self.output_path = os.path.join(self.output_root, f"{base}_mix_{self.session_id}{out_ext}")
        self.is_video = is_video

    # ---------- helpers ----------
    def _run(self, cmd: List[str]) -> None:
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    @staticmethod
    def _esc(s: str) -> str:
        # Escape for filter_complex arguments
        return s.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")

    # ---------- main ----------
    def process(
        self,
        *,
        bgm_db: float = -12.0,         # initial BGM gain in dB (e.g., -12 dB)
        ducking: bool = True,          # enable sidechain ducking
        duck_threshold_db: float = -30.0,
        duck_ratio: float = 8.0,
        duck_attack_ms: int = 10,
        duck_release_ms: int = 250,
        bgm_offset_s: float = 0.0,     # start BGM later (seconds)
        loop_bgm: bool = True,         # loop BGM to match main duration
        master_db: float = 0.0,        # final master gain (dB)
        aac_bitrate: str = "192k"      # video output AAC bitrate
    ) -> MixResult:
        """
        Mix main (video or audio) with a BGM audio track.
        - If main is video: copies video stream; renders mixed audio (AAC).
        - If main is audio: exports MP3 (or you can change below).
        """

        # Inputs:
        #   0: main media (video or audio)
        #   1: bgm audio (optionally -stream_loop -1)

        # Build input command (loop BGM by repeating the BGM input)
        cmd = ["ffmpeg", "-y", "-i", self.main_path]
        if loop_bgm:
            cmd += ["-stream_loop", "-1", "-i", self.bgm_path]
        else:
            cmd += ["-i", self.bgm_path]

        # Filter graph:
        #  [0:a]anull[a0]
        #  [1:a]adelay=offset|offset,volume=bgm_db_dB[minit]
        #  if ducking: [minit][a0]sidechaincompress=... [bgmduck]
        #              [a0][bgmduck]amix=2:normalize=0:duration=first,volume=master_db_dB[outa]
        #  else:       [a0][minit]amix=2:normalize=0:duration=first,volume=master_db_dB[outa]

        adelay_ms = max(0, int(round(bgm_offset_s * 1000)))
        bgm_gain  = f"volume={bgm_db}dB"
        master_gain = f"volume={master_db}dB" if abs(master_db) > 1e-6 else None

        fc_parts = []
        fc_parts.append("[0:a]anull[a0]")
        fc_parts.append(f"[1:a]adelay={adelay_ms}|{adelay_ms},{bgm_gain}[bgm0]")

        if ducking:
            # Compress BGM using main as sidechain detector
            sc = (
                f"sidechaincompress=threshold={duck_threshold_db}dB:ratio={duck_ratio}:"
                f"attack={duck_attack_ms}:release={duck_release_ms}:"
                f"level_in=1:level_sc=1"
            )
            fc_parts.append(f"[bgm0][a0]{sc}[bgmduck]")
            mix_inputs = "[a0][bgmduck]"
        else:
            mix_inputs = "[a0][bgm0]"

        # amix (duration=first → stop when main ends)
        mix = f"{mix_inputs}amix=inputs=2:normalize=0:duration=first[mixed]"
        fc_parts.append(mix)

        # optional master gain
        if master_gain:
            fc_parts.append("[mixed]" + master_gain + "[outa]")
            final_audio = "[outa]"
        else:
            final_audio = "[mixed]"

        filter_complex = ";".join(fc_parts)

        if self.is_video:
            # Keep video, replace audio with mixed
            cmd += [
                "-filter_complex", filter_complex,
                "-map", "0:v:0", "-map", final_audio,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", aac_bitrate,
                "-shortest",  # stop at the end of main video
                self.output_path
            ]
        else:
            # Audio-only output as MP3 (change to AAC/WAV if needed)
            cmd += [
                "-filter_complex", filter_complex,
                "-map", final_audio,
                "-c:a", "libmp3lame", "-b:a", "192k",
                "-shortest",
                self.output_path
            ]

        self._run(cmd)

        return MixResult(
            output_path=self.output_path,
            diagnostics={
                "ducking": ducking,
                "bgm_db": bgm_db,
                "bgm_offset_s": bgm_offset_s,
                "duck": {
                    "threshold_db": duck_threshold_db,
                    "ratio": duck_ratio,
                    "attack_ms": duck_attack_ms,
                    "release_ms": duck_release_ms
                },
                "master_db": master_db,
                "loop_bgm": loop_bgm,
                "is_video": self.is_video
            }
        )
