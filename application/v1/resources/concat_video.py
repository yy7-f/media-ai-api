from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
from application.v1.services.concat_video_service import ConcatVideoService

ns_concat = Namespace(
    "ConcatVideo",
    path="/concat/",
    description="Concatenate multiple videos in order."
)

parser = ns_concat.parser()
parser.add_argument("videos", location="files", type=FileStorage, required=True, action="append",
                    help="Upload 2+ video files in desired order")
parser.add_argument("reencode", location="form", required=False, help="true|false (default true)")
parser.add_argument("audio_bitrate", location="form", required=False, help="AAC bitrate (default 192k)")
parser.add_argument("crf", location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset", location="form", required=False, help="x264 preset (default veryfast)")

@ns_concat.route("/")
class ConcatVideoResource(Resource):
    @ns_concat.expect(parser)
    @ns_concat.doc(description="Concatenate uploaded videos. If reencode=false, inputs must be identical codecs/params.")
    def post(self):
        args = parser.parse_args()
        files = args.get("videos") or []
        if len(files) < 2:
            return {"message": "Please upload at least two video files (in order)."}, 400

        reencode = (request.values.get("reencode","true").lower() == "true")
        audio_bitrate = request.values.get("audio_bitrate","192k")
        crf = request.values.get("crf","18")
        preset = request.values.get("preset","veryfast")

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("CONCAT_OUTPUT", "concat_output")

            paths = ConcatVideoService.save_uploads(files, upload_dir=upload_dir)
            svc = ConcatVideoService(paths, work_root=upload_dir, output_root=output_root)
            res = svc.process(reencode=reencode, audio_bitrate=audio_bitrate, crf=crf, preset=preset)
            svc.cleanup()

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
