from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.audio_denoise_service import AudioDenoiseService

ns_denoise = Namespace(
    "AudioDenoise",
    path="/audio/denoise/",
    description="Audio or video noise reduction using FFmpeg afftdn/arnndn filters."
)

parser = ns_denoise.parser()
parser.add_argument("media", location="files", type=FileStorage, required=True, help="Audio or video file")
parser.add_argument("method", location="form", required=False, help="afftdn|arnndn (default afftdn)")
parser.add_argument("mode", location="form", required=False, help="default|speech|music (default default)")
parser.add_argument("out_format", location="form", required=False, help="wav|m4a (default wav)")

@ns_denoise.route("/")
class AudioDenoiseResource(Resource):
    @ns_denoise.expect(parser)
    @ns_denoise.doc(description="Denoises an uploaded audio or video file.")
    def post(self):
        args = parser.parse_args()
        f = args.get("media")
        if not f:
            return {"message": "No media file provided"}, 400

        method = (request.values.get("method") or "afftdn").lower()
        mode = (request.values.get("mode") or "default").lower()
        out_format = (request.values.get("out_format") or "wav").lower()

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("DENOISE_OUTPUT", "denoise_output")

            path = AudioDenoiseService.save_upload(f, upload_dir=upload_dir)
            svc = AudioDenoiseService(path, work_root=upload_dir, output_root=output_root)
            res = svc.process(method=method, mode=mode, out_format=out_format)

            return jsonify({
                "status": "ok",
                "output": res.output_path,
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
