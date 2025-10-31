import os, json, uuid, subprocess
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class OverlayResult:
    output_path: str
    diagnostics: dict


class OverlayService:
    """
    Draw timed text overlays using ffmpeg drawtext.
    blocks: List[{text, start, end, x, y, fontfile?, fontsize?, color?, box?, boxcolor?}]
    Coordinates in pixels; defaults: center bottom if not provided.
    """

    def __init__(self, video_path: str, output_root="overlay_output"):
        if not os.path.isfile(video_path):
            raise FileNotFoundError(video_path)
        self.video_path = video_path
        base = os.path.splitext(os.path.basename(video_path))[0]
        self.out_root = output_root
        os.makedirs(self.out_root, exist_ok=True)
        self.output_path = os.path.join(self.out_root, f"{base}_overlay.mp4")

    def _run(self, cmd: List[str]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")

    @staticmethod
    def _escape(t: str) -> str:
        # escape for drawtext
        return t.replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")

    def _build_drawtext_chain(self, blocks: List[Dict]) -> str:
        chain = []
        for b in blocks:
            text = self._escape(b.get("text", ""))
            start = float(b.get("start", 0))
            end = float(b.get("end", start + 2))
            # positions
            x = b.get("x", "(w-text_w)/2")
            y = b.get("y", "h-150")
            fontfile = b.get("fontfile")  # optional absolute path to .ttf
            fontsize = int(b.get("fontsize", 36))
            color = b.get("color", "white")
            box = "1" if b.get("box", True) else "0"
            boxcolor = b.get("boxcolor", "black@0.5")

            params = [
                f"text='{text}'",
                f"enable='between(t,{start},{end})'",
                f"x={x}", f"y={y}",
                f"fontsize={fontsize}", f"fontcolor={color}",
                f"box={box}", f"boxcolor={boxcolor}",
                "line_spacing=6",
                "borderw=0"
            ]
            if fontfile:
                params.append(f"fontfile='{fontfile}'")

            chain.append("drawtext=" + ":".join(params))
        return ",".join(chain)

    def render(self, blocks: List[Dict]) -> OverlayResult:
        vf = self._build_drawtext_chain(blocks)
        self._run(["ffmpeg","-y","-i",self.video_path,"-vf",vf,"-c:a","copy", self.output_path])
        return OverlayResult(output_path=self.output_path, diagnostics={"num_blocks": len(blocks)})
