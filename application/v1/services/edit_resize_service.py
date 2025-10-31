import os, uuid, subprocess, shutil
from dataclasses import dataclass
from typing import Optional, Tuple
from werkzeug.utils import secure_filename


@dataclass
class ResizeResult:
    output_path: str
    diagnostics: dict


class EditResizeService:
    ALLOWED = {"mp4","mov","mkv","webm","m4v"}

    @staticmethod
    def allowed_file(name: str) -> bool:
        return "." in name and name.rsplit(".",1)[1].lower() in EditResizeService.ALLOWED

    @staticmethod
    def save_upload(file_storage, upload_dir="uploads") -> str:
        os.makedirs(upload_dir, exist_ok=True)
        name = secure_filename(file_storage.filename or "")
        if not name:
            raise ValueError("Empty filename")
        if not EditResizeService.allowed_file(name):
            raise ValueError("Unsupported video type")
        stem, ext = os.path.splitext(name)
        path = os.path.join(upload_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        file_storage.save(path)
        return path

    def __init__(self, video_path: str, work_root="uploads", output_root="resize_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        self.work_root = work_root
        self.output_root = output_root
        os.makedirs(self.output_root, exist_ok=True)

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.session_id = uuid.uuid4().hex[:8]
        self.output_path = os.path.join(self.output_root, f"{base}_resized_{self.session_id}.mp4")

    # ---------- internals ----------
    def _run(self, cmd):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {' '.join(cmd)}\n{p.stderr or p.stdout}")

    @staticmethod
    def _parse_preset(preset: Optional[str], w: Optional[int], h: Optional[int]) -> Tuple[int,int]:
        """
        Accept presets like:
        - 'portrait_1080x1920'  (9:16)
        - 'landscape_1920x1080' (16:9)
        - 'square_1080'         (1:1)
        Or use explicit width/height if provided.
        """
        if w and h:
            return int(w), int(h)

        if not preset:
            # default TikTok vertical
            return 1080, 1920

        preset = preset.lower().strip()
        if preset == "square_1080":
            return 1080, 1080

        if "x" in preset:
            # e.g. portrait_1080x1920 or 1080x1920
            try:
                tail = preset.split("_")[-1]
                W, H = tail.split("x")
                return int(W), int(H)
            except Exception:
                pass

        # fallback
        return 1080, 1920

    @staticmethod
    def _hex_to_rgb255(hexcode: str) -> Tuple[int,int,int]:
        c = hexcode.strip().lstrip("#")
        if len(c) != 6:
            c = "000000"
        r = int(c[0:2],16); g = int(c[2:4],16); b = int(c[4:6],16)
        return r,g,b

    # ---------- API ----------
    def process(
        self,
        *,
        mode: str = "pad",                 # 'pad' (letterbox) or 'crop' (center-crop)
        preset: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        bg_hex: str = "000000",
        crf: int = 18,
        preset_x264: str = "veryfast",
        fps: Optional[float] = None,
        bitrate_aac: str = "192k",
        copy_audio: bool = True
    ) -> ResizeResult:
        """
        - mode='pad': scale to fit, pad to exact WxH with bg color (keeps full frame; black bars possible)
        - mode='crop': scale to fill, then center crop to exact WxH (no bars; edges may be cut)
        - preset or width/height define target size
        - optional fps override
        """
        W, H = self._parse_preset(preset, width, height)
        r,g,b = self._hex_to_rgb255(bg_hex)

        # Build filterchain (scale + pad/crop)
        # Use mod 2 safe dims for H.264
        # Fit logic using FFmpeg expressions:
        #   fit:   scale='if(gte(iw/ih, W/H), H*iw/ih*? , W) : ...' gets hairy; we use simpler two-step via scale + pad/crop with expressions.
        if mode.lower() == "pad":
            # 1) Scale to fit within WxH (no overflow), preserving aspect
            # 2) Pad to exact WxH with bg color
            vf = (
                f"scale='min({W}/iw,{H}/ih)*iw':'min({W}/iw,{H}/ih)*ih':flags=bicubic,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x{bg_hex}"
            )
        elif mode.lower() == "crop":
            # 1) Scale to fill WxH (cover), preserving aspect
            # 2) Crop center to exact WxH
            vf = (
                f"scale='max({W}/iw,{H}/ih)*iw':'max({W}/iw,{H}/ih)*ih':flags=bicubic,"
                f"crop={W}:{H}"
            )
        else:
            raise ValueError("mode must be 'pad' or 'crop'")

        cmd = ["ffmpeg","-y","-i", self.video_path, "-vf", vf, "-pix_fmt","yuv420p",
               "-c:v","libx264","-preset", preset_x264, "-crf", str(int(crf))]

        if fps:
            cmd.extend(["-r", str(float(fps))])

        if copy_audio:
            cmd.extend(["-c:a","copy"])
        else:
            cmd.extend(["-c:a","aac","-b:a", bitrate_aac])

        cmd.append(self.output_path)
        self._run(cmd)

        return ResizeResult(
            output_path=self.output_path,
            diagnostics={
                "mode": mode,
                "target_w": W, "target_h": H,
                "bg_hex": bg_hex,
                "crf": crf,
                "preset": preset_x264,
                "fps": fps,
                "copy_audio": copy_audio
            }
        )
