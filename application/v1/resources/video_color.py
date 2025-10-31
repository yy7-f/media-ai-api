from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.video_color_service import VideoColorService

ns_color = Namespace(
    "VideoColor",
    path="/video/effects/color/",
    description="Apply color filters or LUTs to video using FFmpeg (CPU-only)."
)

parser = ns_color.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True)
parser.add_argument("mode", location="form", required=False, help="grayscale|sepia|bw_highcontrast|cinematic|brightness|contrast|saturation|lut")
parser.add_argument("value", location="form", required=False, help="Numeric value for brightness/contrast/saturation (optional)")
parser.add_argument("lut_path", location="form", required=False, help="Path to LUT .cube file (for mode=lut)")
parser.add_argument("crf", location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset", location="form", required=False, help="x264 preset (default veryfast)")
parser.add_argument("copy_audio", location="form", required=False, help="true|false (default true)")

@ns_color.route("/")
class VideoColorResource(Resource):
    @ns_color.expect(parser)
    @ns_color.doc(description="Apply cinematic, grayscale, sepia, or LUT-based effects to a video.")
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video provided"}, 400

        def to_float(v):
            try: return float(v) if v not in (None, "") else None
            except Exception: return None
        def to_int(v, d):
            try: return int(v) if v not in (None, "") else d
            except Exception: return d
        def to_bool(v, d):
            if v is None: return d
            return str(v).lower() == "true"

        mode       = request.values.get("mode", "cinematic")
        value      = to_float(request.values.get("value"))
        lut_path   = request.values.get("lut_path")
        crf        = to_int(request.values.get("crf"), 18)
        preset     = request.values.get("preset", "veryfast")
        copy_audio = to_bool(request.values.get("copy_audio"), True)

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("COLOR_OUTPUT", "color_output")

            vpath = VideoColorService.save_upload(f, upload_dir=upload_dir)
            svc = VideoColorService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                mode=mode, value=value, lut_path=lut_path,
                crf=crf, preset=preset, copy_audio=copy_audio
            )

            return jsonify({
                "status": "ok",
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
