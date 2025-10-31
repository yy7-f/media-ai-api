import os
import uuid
import shutil
import cv2
import subprocess
import easyocr
from werkzeug.utils import secure_filename


class InpaintImageService:
    def __init__(self, image_path: str, work_root: str = "uploads", output_root: str = "inpaint_output"):
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"Input image not found: {image_path}")

        self.image_path = image_path
        self.work_root = work_root
        self.output_root = output_root
        self.session_id = uuid.uuid4().hex[:8]

        base = os.path.splitext(os.path.basename(self.image_path))[0]
        self.session_dir = os.path.join(self.work_root, f"{base}_{self.session_id}")
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.output_root, exist_ok=True)

        self.mask_path = os.path.join(self.session_dir, f"{base}_mask.png")
        self.output_path = os.path.join(self.output_root, f"{base}_inpainted_{self.session_id}.png")

    # ---------- Helpers ----------
    @staticmethod
    def allowed_file(filename):
        allowed = {"png", "jpg", "jpeg", "webp"}
        return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads", suffix=""):
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(file_storage.filename or "")
        if not filename:
            raise ValueError("Empty filename")
        if not InpaintImageService.allowed_file(filename):
            raise ValueError("Unsupported file type")
        stem, ext = os.path.splitext(filename)
        unique_name = f"{stem}_{uuid.uuid4().hex[:8]}{suffix}{ext}"
        path = os.path.join(upload_dir, unique_name)
        file_storage.save(path)
        return path

    # ---------- Core logic ----------
    def process_lama(self, ocr_langs="en", device="cpu"):
        # Step 1: Detect text areas via OCR
        reader = easyocr.Reader(ocr_langs.split(","))
        img = cv2.imread(self.image_path)
        mask = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mask[:] = 0
        results = reader.readtext(self.image_path)
        for (bbox, _, _) in results:
            pt1, pt2 = tuple(map(int, bbox[0])), tuple(map(int, bbox[2]))
            cv2.rectangle(mask, pt1, pt2, 255, -1)
        cv2.imwrite(self.mask_path, mask)

        # Step 2: Run LaMa Cleaner via iopaint CLI
        cmd = [
            "iopaint", "run",
            "--model", "lama",
            "--device", device,
            "--image", self.image_path,
            "--mask", self.mask_path,
            "--output", self.output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"LaMa inpainting failed: {result.stderr}")

        return {
            "output_path": self.output_path,
            "filename": os.path.basename(self.output_path),
            "diagnostics": {
                "ocr_langs": ocr_langs,
                "device": device,
                "ocr_detected_boxes": len(results),
            },
        }

    def cleanup(self):
        try:
            if os.path.isdir(self.session_dir):
                shutil.rmtree(self.session_dir, ignore_errors=True)
        except Exception:
            pass
