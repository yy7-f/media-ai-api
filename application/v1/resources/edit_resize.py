from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.edit_resize_service import EditResizeService

ns_resize = Namespace(
    "EditResize",
    path="/edit/resize/",
    description="Resize videos to a target aspect/size via pad (letterbox) or crop (center-crop)."
)

parser = ns_resize.parser()
parser.add_argument("video",  location="files", type=FileStorage, required=True, help="Video file")
parser.add_argument("mode",   location="form", required=False, help="pad|crop (default pad)")
parser.add_argument("preset", location="form", required=False, help="portrait_1080x1920 | landscape_1920x1080 | square_1080 | or WIDTHxHEIGHT")
parser.add_argument("width",  location="form", required=False, help="Override width (int)")
parser.add_argument("height", location="form", required=False, help="Override height (int)")
parser.add_argument("bg_hex", location="form", required=False, help="Padding color hex (default 000000)")
parser.add_argument("crf",    location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset_x264", location="form", required=False, help="x264 preset (default veryfast)")
parser.add_argument("fps",    location="form", required=False, help="Output FPS (optional)")
parser.add_argument("copy_audio", location="form", required=False, help="true|false (default true)")
parser.add_argument("bitrate_aac", location="form", required=False, help="AAC bitrate if re-encoding audio (default 192k)")

@ns_resize.route("/")
class EditResizeResource(Resource):
    @ns_resize.expect(parser)
    @ns_resize.doc(description="Resize with pad (letterbox) or crop (fill). Provide either a preset or explicit width/height.")
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video provided"}, 400

        mode   = (request.values.get("mode") or "pad").lower()
        preset = request.values.get("preset")
        width  = request.values.get("width")
        height = request.values.get("height")
        bg_hex = (request.values.get("bg_hex") or "000000").upper()

        try:
            width  = int(width)  if width  not in (None,"") else None
            height = int(height) if height not in (None,"") else None
        except ValueError:
            return {"message": "width/height must be integers"}, 400

        try:
            crf = int(request.values.get("crf", 18))
        except ValueError:
            crf = 18

        preset_x264 = request.values.get("preset_x264", "veryfast")
        fps_raw = request.values.get("fps")
        fps = float(fps_raw) if fps_raw not in (None, "") else None

        copy_audio = (request.values.get("copy_audio","true").lower() == "true")
        bitrate_aac = request.values.get("bitrate_aac", "192k")

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("RESIZE_OUTPUT", "resize_output")

            vpath = EditResizeService.save_upload(f, upload_dir=upload_dir)
            svc = EditResizeService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                mode=mode, preset=preset, width=width, height=height,
                bg_hex=bg_hex, crf=crf, preset_x264=preset_x264,
                fps=fps, bitrate_aac=bitrate_aac, copy_audio=copy_audio
            )
            return jsonify({
                "status":"ok",
                "result_path": res.output_path,
                "filename": res.output_path.split("/")[-1],
                "diagnostics": res.diagnostics
            })
        except ValueError as ve:
            return {"message": str(ve)}, 400
        except FileNotFoundError as fe:
            return {"message": str(fe)}, 404
        except RuntimeError as re:
            return {"message": str(re)}, 500
        except Exception as e:
            return {"message": f"Unexpected error: {e}"}, 500
