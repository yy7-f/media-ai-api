from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
import os

from application.v1.services.video_trim_service import VideoTrimService

ns_trim = Namespace(
    "VideoTrim",
    path="/video/trim/",
    description="Trim video by time range (precise re-encode or fast keyframe copy)."
)

parser = ns_trim.parser()
parser.add_argument("video",    location="files", type=FileStorage, required=True)
parser.add_argument("start",    location="form", required=False, help="Start time in seconds (default 0)")
parser.add_argument("end",      location="form", required=False, help="End time in seconds (exclusive)")
parser.add_argument("duration", location="form", required=False, help="Duration in seconds (alternative to end)")
parser.add_argument("precise",  location="form", required=False, help="true|false (default true)")
parser.add_argument("crf",      location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset",   location="form", required=False, help="x264 preset (default veryfast)")
parser.add_argument("copy_audio", location="form", required=False, help="true|false (default true)")

@ns_trim.route("/")
class VideoTrimResource(Resource):
    @ns_trim.expect(parser)
    @ns_trim.doc(description="Cut a section from the uploaded video.")
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video provided"}, 400

        # helpers
        def to_float(v, d):
            try: return float(v) if v not in (None, "") else d
            except ValueError: return d
        def to_int(v, d):
            try: return int(v) if v not in (None, "") else d
            except ValueError: return d
        def to_bool(v, d):
            if v is None: return d
            return str(v).lower() == "true"

        start    = to_float(request.values.get("start"), None)
        end      = to_float(request.values.get("end"), None)
        duration = to_float(request.values.get("duration"), None)
        precise  = to_bool(request.values.get("precise"), True)
        crf      = to_int(request.values.get("crf"), 18)
        preset   = request.values.get("preset", "veryfast")
        copy_a   = to_bool(request.values.get("copy_audio"), True)

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("TRIM_OUTPUT", "trim_output")
            bucket_name = current_app.config.get("OUTPUT_BUCKET", "media-ai-api-output")

            vpath = VideoTrimService.save_upload(f, upload_dir=upload_dir)
            svc = VideoTrimService(vpath, work_root=upload_dir, output_root=output_root)

            res = svc.process(
                start=start, end=end, duration=duration,
                precise=precise, crf=crf, preset=preset, copy_audio=copy_a,
                bucket_name=bucket_name,
            )

            return jsonify({
                "status": "ok",
                "result_path": res.output_path,
                "filename": res.output_path.split("/")[-1],
                "diagnostics": res.diagnostics,
                "gcs_uri": res.diagnostics.get("gcs_url"),
            })
        except ValueError as ve:
            return {"message": str(ve)}, 400
        except FileNotFoundError as fe:
            return {"message": str(fe)}, 404
        except RuntimeError as re:
            return {"message": str(re)}, 500
        except Exception as e:
            return {"message": f"Unexpected error: {e}"}, 500
