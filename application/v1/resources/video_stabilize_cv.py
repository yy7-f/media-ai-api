from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.video_stabilize_cv_service import VideoStabilizeCVService

ns_stab_cv = Namespace(
    "VideoStabilizeCV",
    path="/video/stabilize-cv/",
    description="OpenCV-based video stabilization (optical flow + trajectory smoothing)."
)

parser = ns_stab_cv.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video file")
parser.add_argument("smoothing_radius", location="form", required=False, help="Moving-average radius in frames (default 30)")
parser.add_argument("max_corners",      location="form", required=False, help="Features per frame (default 400)")
parser.add_argument("quality_level",    location="form", required=False, help="Shi-Tomasi qualityLevel (0..1, default 0.01)")
parser.add_argument("min_distance",     location="form", required=False, help="Min feature distance (default 30)")
parser.add_argument("ransac_reproj_thresh", location="form", required=False, help="Affine RANSAC reproj threshold (default 3.0)")
parser.add_argument("border_mode",      location="form", required=False, help="black|reflect|replicate (default black)")
parser.add_argument("zoom_percent",     location="form", required=False, help="Crop/zoom to hide borders (default 5.0)")
parser.add_argument("keep_audio",       location="form", required=False, help="true|false (default true)")
parser.add_argument("crf",              location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset",           location="form", required=False, help="x264 preset (default veryfast)")

@ns_stab_cv.route("/")
class VideoStabilizeCVResource(Resource):
    @ns_stab_cv.expect(parser)
    @ns_stab_cv.doc(description="Stabilizes the uploaded video using OpenCV (no vid.stab dependency).")
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video provided"}, 400

        def to_int(v, d):
            try: return int(v) if v not in (None,"") else d
            except ValueError: return d
        def to_float(v, d):
            try: return float(v) if v not in (None,"") else d
            except ValueError: return d
        def to_bool(v, d):
            if v is None: return d
            return str(v).lower() == "true"

        smoothing_radius   = to_int(request.values.get("smoothing_radius"), 30)
        max_corners        = to_int(request.values.get("max_corners"), 400)
        quality_level      = to_float(request.values.get("quality_level"), 0.01)
        min_distance       = to_int(request.values.get("min_distance"), 30)
        ransac_thresh      = to_float(request.values.get("ransac_reproj_thresh"), 3.0)
        border_mode        = request.values.get("border_mode", "black")
        zoom_percent       = to_float(request.values.get("zoom_percent"), 5.0)
        keep_audio         = to_bool(request.values.get("keep_audio"), True)
        crf                = to_int(request.values.get("crf"), 18)
        preset             = request.values.get("preset", "veryfast")

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("STABILIZE_CV_OUTPUT", "stabilize_cv_output")

            vpath = VideoStabilizeCVService.save_upload(f, upload_dir=upload_dir)
            svc = VideoStabilizeCVService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                smoothing_radius=smoothing_radius,
                max_corners=max_corners,
                quality_level=quality_level,
                min_distance=min_distance,
                ransac_reproj_thresh=ransac_thresh,
                border_mode=border_mode,
                zoom_percent=zoom_percent,
                keep_audio=keep_audio,
                crf=crf,
                preset=preset
            )
            svc.cleanup()

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
