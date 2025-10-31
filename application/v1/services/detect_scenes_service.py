import os, uuid, re, json, subprocess, shutil
from dataclasses import dataclass
from typing import List, Dict, Optional
from werkzeug.utils import secure_filename


@dataclass
class SceneDetectResult:
    json_path: str
    timestamps: List[float]
    thumbnails_dir: Optional[str]
    diagnostics: Dict


class DetectScenesService:
    ALLOWED = {"mp4","mov","mkv","webm","m4v"}

    @staticmethod
    def allowed_file(name: str) -> bool:
        return "." in name and name.rsplit(".",1)[1].lower() in DetectScenesService.ALLOWED

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not DetectScenesService.allowed_file(name):
            raise ValueError("Unsupported file type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, video_path: str, work_root="uploads", output_root="scenes_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.session_dir = os.path.join(work_root, f"{base}_{self.session_id}")
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.output_root, exist_ok=True)

        self.json_path = os.path.join(self.output_root, f"{base}_scenes_{self.session_id}.json")
        self.thumbs_dir = os.path.join(self.output_root, f"{base}_thumbs_{self.session_id}")

    # ---------- helpers ----------
    def _run(self, cmd: List[str]) -> subprocess.CompletedProcess:
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")
        return p

    def _probe_duration(self) -> Optional[float]:
        p = self._run([
            "ffprobe","-v","error",
            "-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1",
            self.video_path
        ])
        try:
            return float((p.stdout or "").strip())
        except Exception:
            return None

    # ---------- core ----------
    def process(
        self,
        *,
        threshold: float = 0.3,          # ffmpeg scene score threshold
        include_start: bool = True,      # add 0.0 as first scene boundary
        include_end: bool = False,       # add duration as last boundary
        min_gap_sec: float = 0.0,        # merge adjacent detections closer than this
        save_thumbs: bool = False,       # export a PNG at each boundary
        thumb_scale: Optional[int] = 480 # scale shorter side to this (keeps aspect); None = raw frame
    ) -> SceneDetectResult:

        # Detect scene changes using select + showinfo (+ metadata for score)
        # We parse pts_time from showinfo; scene score from metadata=print when available.
        filtergraph = f"select='gt(scene,{threshold})',showinfo,metadata=print"
        p = self._run([
            "ffmpeg","-hide_banner","-nostdin","-y",
            "-i", self.video_path,
            "-vf", filtergraph,
            "-f","null","-"
        ])
        log = (p.stderr or "") + (p.stdout or "")

        # Parse times and scores
        # showinfo lines often have "pts_time:123.456"
        ts = [float(x) for x in re.findall(r"pts_time:(\d+\.?\d*)", log)]
        # metadata prints like "lavfi.scene_score=0.45321"
        scores = [float(x) for x in re.findall(r"lavfi\.scene_score=(\d+\.?\d*)", log)]

        # De-dup + sort
        times = sorted(set(round(t, 3) for t in ts))

        # Optionally add start/end
        duration = self._probe_duration()
        if include_start and (not times or times[0] > 0.01):
            times = [0.0] + times
        if include_end and duration and (not times or abs(times[-1] - duration) > 1e-3):
            times.append(round(duration, 3))

        # Merge small gaps
        if min_gap_sec > 0 and len(times) > 1:
            merged = [times[0]]
            for t in times[1:]:
                if (t - merged[-1]) < float(min_gap_sec):
                    continue
                merged.append(t)
            times = merged

        # Save JSON
        payload = {
            "video": os.path.basename(self.video_path),
            "threshold": threshold,
            "include_start": include_start,
            "include_end": include_end,
            "min_gap_sec": min_gap_sec,
            "duration": duration,
            "count": len(times),
            "timestamps": times,
            "scores_hint": scores[:len(times)] if scores else None
        }
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        thumbs_dir = None
        if save_thumbs and times:
            os.makedirs(self.thumbs_dir, exist_ok=True)
            thumbs_dir = self.thumbs_dir
            # Extract a single frame at each timestamp (use -ss before -i for speed)
            # Scale while preserving AR: scale=iw*min(1,SW/iw):ih*min(1,SH/ih) is messy; we’ll use shorter-side logic:
            scale_filter = None
            if thumb_scale:
                # Fit so that the shorter side == thumb_scale, keeping aspect (round to even)
                scale_filter = f"scale='if(lt(iw,ih),{thumb_scale},-2)':'if(lt(iw,ih),-2,{thumb_scale})':flags=bicubic"

            for idx, t in enumerate(times, start=1):
                out_path = os.path.join(thumbs_dir, f"scene_{idx:04d}.png")
                cmd = ["ffmpeg","-hide_banner","-nostdin","-y","-ss", f"{t:.3f}","-i", self.video_path,"-frames:v","1"]
                if scale_filter:
                    cmd += ["-vf", scale_filter]
                cmd += [out_path]
                self._run(cmd)

        return SceneDetectResult(
            json_path=self.json_path,
            timestamps=times,
            thumbnails_dir=thumbs_dir,
            diagnostics={
                "num_scenes": len(times),
                "duration": duration,
                "threshold": threshold,
                "saved_thumbs": bool(thumbs_dir)
            }
        )

    def cleanup(self):
        try:
            shutil.rmtree(self.session_dir, ignore_errors=True)
        except Exception:
            pass
