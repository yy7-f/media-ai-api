import os, uuid, subprocess, shutil, zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from werkzeug.utils import secure_filename


@dataclass
class BatchColorItem:
    input_path: str
    output_path: str
    ok: bool
    error: Optional[str]
    filter_used: str


@dataclass
class BatchColorResult:
    outputs: List[BatchColorItem]
    zipped_path: Optional[str]        # path to .zip if make_zip=True, else None
    diagnostics: Dict


class VideoColorBatchService:
    ALLOWED = {"mp4", "mov", "mkv", "webm", "m4v"}

    @staticmethod
    def allowed(name: str) -> bool:
        return "." in name and name.rsplit(".", 1)[1].lower() in VideoColorBatchService.ALLOWED

    @staticmethod
    def save_uploads(files: List, upload_dir="uploads") -> List[str]:
        os.makedirs(upload_dir, exist_ok=True)
        paths = []
        for fs in files:
            name = secure_filename(fs.filename or "")
            if not name:
                raise ValueError("One of the files has an empty filename")
            if not VideoColorBatchService.allowed(name):
                raise ValueError(f"Unsupported video type: {name}")
            stem, ext = os.path.splitext(name)
            path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
            fs.save(path)
            paths.append(path)
        if not paths:
            raise ValueError("No valid videos uploaded")
        return paths

    def __init__(self, video_paths: List[str], work_root="uploads", output_root="color_output"):
        if not video_paths:
            raise ValueError("video_paths must be non-empty")
        for p in video_paths:
            if not os.path.isfile(p):
                raise FileNotFoundError(p)

        self.video_paths = video_paths
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        self.session_id = uuid.uuid4().hex[:8]

    # ---------- internals ----------
    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode == 0, (p.stderr or p.stdout)

    @staticmethod
    def _build_filter(mode: str, value: Optional[float], lut_path: Optional[str]) -> str:
        m = (mode or "cinematic").lower()
        if m == "grayscale":
            return "hue=s=0"
        elif m == "sepia":
            return "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131"
        elif m == "bw_highcontrast":
            return "hue=s=0,eq=contrast=1.5:brightness=0.05"
        elif m == "cinematic":
            return "curves=preset=medium_contrast,eq=contrast=1.15:saturation=1.05,curves=blue='0/0 0.45/0.43 1/0.9'"
        elif m == "brightness":
            val = value if value is not None else 0.1
            return f"eq=brightness={val}"
        elif m == "contrast":
            val = value if value is not None else 1.2
            return f"eq=contrast={val}"
        elif m == "saturation":
            val = value if value is not None else 1.2
            return f"eq=saturation={val}"
        elif m == "lut":
            if not lut_path or not os.path.isfile(lut_path):
                raise ValueError("Missing or invalid LUT file path for mode=lut")
            return f"lut3d=file='{lut_path}'"
        else:
            raise ValueError(f"Unknown mode: {mode}")

    # ---------- public ----------
    def process(self,
                *,
                mode: str = "cinematic",
                value: Optional[float] = None,
                lut_path: Optional[str] = None,
                crf: int = 18,
                preset: str = "veryfast",
                copy_audio: bool = True,
                make_zip: bool = False,
                target_resolution: Optional[str] = None  # WIDTHxHEIGHT, e.g., 1920x1080
                ) -> BatchColorResult:

        vf_base = self._build_filter(mode, value, lut_path)
        items: List[BatchColorItem] = []

        # Validate/prepare scale filter if requested
        scale_suffix = ""
        if target_resolution:
            try:
                w_str, h_str = target_resolution.lower().split("x")
                w, h = int(w_str), int(h_str)
                if w <= 0 or h <= 0:
                    raise ValueError
                scale_suffix = f",scale={w}:{h}"
            except Exception:
                raise ValueError(f"Invalid target_resolution format: {target_resolution} (expected WIDTHxHEIGHT)")

        for inp in self.video_paths:
            base = os.path.splitext(os.path.basename(inp))[0]
            outp = os.path.join(self.output_root, f"{base}_color_{self.session_id}.mp4")

            vf = vf_base + scale_suffix

            cmd = [
                "ffmpeg", "-y", "-i", inp,
                "-vf", vf,
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-pix_fmt", "yuv420p"
            ]
            if copy_audio:
                cmd += ["-c:a", "copy"]
            else:
                cmd += ["-an"]
            cmd += [outp]

            ok, err = self._run(cmd)
            items.append(BatchColorItem(
                input_path=inp,
                output_path=outp if ok else "",
                ok=ok,
                error=None if ok else err,
                filter_used=vf
            ))

        zip_path = None
        if make_zip:
            zip_name = os.path.join(self.output_root, f"color_batch_{self.session_id}.zip")
            with zipfile.ZipFile(zip_name, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for it in items:
                    if it.ok and os.path.isfile(it.output_path):
                        zf.write(it.output_path, arcname=os.path.basename(it.output_path))
            zip_path = zip_name

        return BatchColorResult(
            outputs=items,
            zipped_path=zip_path,
            diagnostics={
                "mode": mode,
                "value": value,
                "lut_path": lut_path,
                "crf": crf,
                "preset": preset,
                "copy_audio": copy_audio,
                "zip": make_zip,
                "count": len(items),
                "target_resolution": target_resolution,
                "session_id": self.session_id
            }
        )
