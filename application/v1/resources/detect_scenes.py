from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.detect_scenes_service import DetectScenesService

ns_scenes = Namespace(
    "DetectScenes",
    path="/detect/scenes/",
    description="Detect scene boundaries via FFmpeg (gt(scene,threshold))."
)

parser = ns_scenes.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video file")
parser.add_argument("threshold", location="form", required=False, help="Scene threshold (0.0–1.0, default 0.3)")
parser.add_argument("include_start", location="form", required=False, help="true|false (default true)")
parser.add_argument("include_end", location="form", required=False, help="true|false (default false)")
parser.add_argument("min_gap_sec", location="form", required=False, help="Merge detections closer than this (default 0)")
parser.add_argument("save_thumbs", location="form", required=False, help="true|false (default false)")
parser.add_argument("thumb_scale", location="form", required=False, help="Shorter side px for thumbs (default 480)")

@ns_scenes.route("/")
class DetectScenesResource(Resource):
    @ns_scenes.expect(parser)
    @ns_scenes.doc(description="Returns JSON with scene timestamps; optionally exports thumbnails.")
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video provided"}, 400

        def to_float(v, d):
            try: return float(v) if v not in (None,"") else d
            except ValueError: return d
        def to_bool(v, d):
            if v is None: return d
            return str(v).lower() == "true"
        def to_int(v, d):
            try: return int(v) if v not in (None,"") else d
            except ValueError: return d

        thr = to_float(request.values.get("threshold"), 0.3)
        include_start = to_bool(request.values.get("include_start"), True)
        include_end   = to_bool(request.values.get("include_end"), False)
        min_gap_sec   = to_float(request.values.get("min_gap_sec"), 0.0)
        save_thumbs   = to_bool(request.values.get("save_thumbs"), False)
        thumb_scale   = request.values.get("thumb_scale")
        thumb_scale   = to_int(thumb_scale, 480)

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("SCENES_OUTPUT", "scenes_output")

            vpath = DetectScenesService.save_upload(f, upload_dir=upload_dir)
            svc = DetectScenesService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                threshold=thr,
                include_start=include_start,
                include_end=include_end,
                min_gap_sec=min_gap_sec,
                save_thumbs=save_thumbs,
                thumb_scale=thumb_scale
            )
            svc.cleanup()

            return jsonify({
                "status": "ok",
                "json": res.json_path,
                "timestamps": res.timestamps,
                "thumbnails_dir": res.thumbnails_dir,
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
