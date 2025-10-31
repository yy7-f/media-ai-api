import os
import uuid
import shutil
import subprocess
import traceback
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

from flask import current_app, request
from werkzeug.utils import secure_filename

import cv2
import easyocr


ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}
DEFAULT_FPS = 30
DEFAULT_LANGS = "en"
DEFAULT_DEVICE = "cpu"   # "cpu" or "cuda"


def _ext_ok(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_VIDEO_EXTS


def _check_dep(cmd: str):
    """Ensure a command exists (ffmpeg, iopaint)."""
    try:
        subprocess.run([cmd, "-h"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        raise RuntimeError(f"Required dependency '{cmd}' not found on PATH.")


def _run(cmd: list):
    """Run a subprocess with error bubbling and quiet logs."""
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n{res.stderr.decode(errors='ignore')}"
        )
    return res


@dataclass
class InpaintArgs:
    input_path: str
    output_path: str
    ocr_langs: str = DEFAULT_LANGS
    fps: int = DEFAULT_FPS
    device: str = DEFAULT_DEVICE
    job_root: Optional[str] = None  # a unique folder per job


class _Pipeline:
    """Internal pipeline runner—stateless except for paths."""

    def __init__(self, args: InpaintArgs):
        self.args = args
        self.frames_dir = os.path.join(args.job_root, "frames")
        self.masks_dir = os.path.join(args.job_root, "masks")
        self.inpainted_dir = os.path.join(args.job_root, "inpainted")

        # Fresh job dirs
        if os.path.exists(args.job_root):
            shutil.rmtree(args.job_root)
        os.makedirs(self.frames_dir, exist_ok=True)
        os.makedirs(self.masks_dir, exist_ok=True)
        os.makedirs(self.inpainted_dir, exist_ok=True)

    def extract_frames(self):
        _run([
            "ffmpeg", "-y", "-i", self.args.input_path,
            f"{self.frames_dir}/frame_%05d.png",
            "-hide_banner", "-loglevel", "error"
        ])

    def generate_masks(self):
        reader = easyocr.Reader(
            self.args.ocr_langs.split(","), gpu=(self.args.device.lower() == "cuda")
        )
        frame_files = sorted(f for f in os.listdir(self.frames_dir) if f.endswith(".png"))
        for frame in frame_files:
            frame_path = os.path.join(self.frames_dir, frame)
            img = cv2.imread(frame_path)
            if img is None:
                continue
            mask = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            mask[:] = 0
            results = reader.readtext(frame_path)
            # results: list of (bbox, text, conf), bbox is 4 points
            for (bbox, _, _) in results:
                pt1 = tuple(map(int, bbox[0]))
                pt3 = tuple(map(int, bbox[2]))
                cv2.rectangle(mask, pt1, pt3, 255, -1)
            cv2.imwrite(os.path.join(self.masks_dir, frame), mask)

    def inpaint(self):
        _run([
            "iopaint", "run",
            "--model", "lama",
            "--device", self.args.device,
            "--image", self.frames_dir,
            "--mask", self.masks_dir,
            "--output", self.inpainted_dir
        ])

    def reassemble(self):
        _run([
            "ffmpeg", "-y",
            "-framerate", str(self.args.fps),
            "-i", f"{self.inpainted_dir}/frame_%05d.png",
            "-i", self.args.input_path,
            "-map", "0:v", "-map", "1:a?",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-shortest",
            self.args.output_path,
            "-hide_banner", "-loglevel", "error"
        ])

    def run(self) -> str:
        _check_dep("ffmpeg")
        _check_dep("iopaint")
        self.extract_frames()
        self.generate_masks()
        self.inpaint()
        self.reassemble()
        return self.args.output_path


class TextInpaintService:
    """
    Flask-RESTX-friendly wrapper. Mirrors SpleeterService style:
        response, code = TextInpaintService().process()
    Reads from flask.request (file + form fields) and returns JSON + HTTP status.
    """

    def __init__(self):
        # Allow overriding these dirs via app config; fallback to sensible defaults
        app = current_app
        self.upload_dir = os.path.abspath(app.config.get("UPLOAD_DIR", "uploads"))
        self.output_dir = os.path.abspath(app.config.get("OUTPUT_DIR", "outputs"))
        self.jobs_dir = os.path.abspath(app.config.get("JOBS_DIR", "jobs"))
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.jobs_dir, exist_ok=True)

    def _save_upload(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        if "file" not in request.files:
            return None, "No file part", None

        f = request.files["file"]
        if f.filename == "":
            return None, "Empty filename", None

        if not _ext_ok(f.filename):
            return None, f"Unsupported file type. Allowed: {sorted(ALLOWED_VIDEO_EXTS)}", None

        base = os.path.splitext(secure_filename(f.filename))[0]
        job_id = str(uuid.uuid4())
        input_path = os.path.join(self.upload_dir, f"{base}_{job_id}.mp4")
        f.save(input_path)
        return input_path, None, job_id

    def process(self) -> Tuple[Dict[str, Any], int]:
        try:
            input_path, err, job_id = self._save_upload()
            if err:
                return {"error": err}, 400

            # Params
            form = request.form
            ocr_langs = form.get("ocr_langs", DEFAULT_LANGS)
            try:
                fps = int(form.get("fps", DEFAULT_FPS))
            except Exception:
                return {"error": "fps must be an integer"}, 400
            device = form.get("device", DEFAULT_DEVICE).lower()
            if device not in {"cpu", "cuda"}:
                return {"error": "device must be 'cpu' or 'cuda'"}, 400

            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(self.output_dir, f"{base_name}_no_text.mp4")
            job_root = os.path.join(self.jobs_dir, job_id)

            args = InpaintArgs(
                input_path=input_path,
                output_path=output_path,
                ocr_langs=ocr_langs,
                fps=fps,
                device=device,
                job_root=job_root,
            )
            pipeline = _Pipeline(args)
            final_path = pipeline.run()

            # You can serve files with a separate /files/<path> endpoint in your app
            rel_output = os.path.relpath(final_path, self.output_dir)
            download_url = f"/files/{rel_output}"

            return {
                "job_id": job_id,
                "output_file": f"outputs/{rel_output}",
                "download_url": download_url,
                "params": {"ocr_langs": ocr_langs, "fps": fps, "device": device},
            }, 200

        except Exception as e:
            traceback.print_exc()
            return {"error": str(e)}, 500
