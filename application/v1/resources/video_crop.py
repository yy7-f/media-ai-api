from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.video_crop_service import VideoCropService

ns_crop = Namespace(
    "VideoCrop",
    path="/video/crop/",
    description="Crop rectangle OR aspect crop with placement (center/top/bottom/left/right/corners)."
)

parser = ns_crop.parser()
parser.add_argument("video",  location="files", type=FileStorage, required=True)

# Manual rectangle (takes precedence if all four are provided)
parser.add_argument("x",      location="form", required=False)
parser.add_argument("y",      location="form", required=False)
parser.add_argument("width",  location="form", required=False)
parser.add_argument("height", location="form", required=False)

# Aspect + placement
parser.add_argument("aspect",  location="form", required=False, help="e.g., 1:1, 9:16, 16:9, 4:5")
parser.add_argument("mode",    location="form", required=False, help="center|top|bottom|left|right|top-left|top-right|bottom-left|bottom-right (default center)")
parser.add_argument("offset_x",location="form", required=False, help="Nudge X pixels after placement (default 0)")
parser.add_argument("offset_y",location="form", required=False, help="Nudge Y pixels after placement (default 0)")

# Common
parser.add_argument("ensure_even", location="form", required=False, help="true|false (default true)")
parser.add_argument("safe_bounds", location="form", required=False, help="true|false (default true)")
parser.add_argument("crf",         location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset",      location="form", required=False, help="x264 preset (default veryfast)")
parser.add_argument("copy_audio",  location="form", required=False, help="true|false (default true)")

@ns_crop.route("/")
class VideoCropResource(Resource):
    @ns_crop.expect(parser)
    @ns_crop.doc(description="Provide either x,y,width,height OR aspect + mode; output re-encodes video (x264).")
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video provided"}, 400

        def to_int_opt(v):
            try: return int(v) if v not in (None, "") else None
            except Exception: return None
        def to_bool(v, d):
            if v is None: return d
            return str(v).lower() == "true"
        def to_int(v, d):
            try: return int(v) if v not in (None, "") else d
            except Exception: return d

        # Manual rect (optional)
        x      = to_int_opt(request.values.get("x"))
        y      = to_int_opt(request.values.get("y"))
        width  = to_int_opt(request.values.get("width"))
        height = to_int_opt(request.values.get("height"))

        aspect   = request.values.get("aspect")
        mode     = request.values.get("mode", "center")
        offset_x = to_int(request.values.get("offset_x"), 0)
        offset_y = to_int(request.values.get("offset_y"), 0)

        ensure_even = to_bool(request.values.get("ensure_even"), True)
        safe_bounds = to_bool(request.values.get("safe_bounds"), True)
        crf         = to_int(request.values.get("crf"), 18)
        preset      = request.values.get("preset", "veryfast")
        copy_a      = to_bool(request.values.get("copy_audio"), True)

        manual_ok = all(v is not None for v in (x, y, width, height))
        if not manual_ok and not aspect:
            return {"message": "Provide either x,y,width,height OR aspect=9:16"}, 400

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("CROP_OUTPUT", "crop_output")

            vpath = VideoCropService.save_upload(f, upload_dir=upload_dir)
            svc = VideoCropService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                x=x, y=y, width=width, height=height,
                aspect=aspect, mode=mode,
                offset_x=offset_x, offset_y=offset_y,
                ensure_even=ensure_even, safe_bounds=safe_bounds,
                crf=crf, preset=preset, copy_audio=copy_a
            )

            return jsonify({
                "status": "ok",
                "result_path": res.output_path,
                "filename": res.output_path.split('/')[-1],
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
