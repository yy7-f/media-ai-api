from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.audio_normalize_service import AudioNormalizeService

ns_anorm = Namespace(
    "AudioNormalize",
    path="/audio/normalize/",
    description="Two-pass EBU R128 loudness normalization (FFmpeg loudnorm)."
)

parser = ns_anorm.parser()
parser.add_argument("media", location="files", type=FileStorage, required=True,
                    help="Audio or Video file")
parser.add_argument("target_i",  location="form", required=False, help="Target LUFS (default -14)")
parser.add_argument("target_tp", location="form", required=False, help="True Peak dBTP (default -1.5)")
parser.add_argument("target_lra",location="form", required=False, help="Loudness Range LRA (default 11)")
parser.add_argument("audio_output", location="form", required=False,
                    help="If audio input: mp3|wav|m4a (default mp3)")
parser.add_argument("aac_bitrate", location="form", required=False,
                    help="If video input: AAC bitrate (default 192k)")

@ns_anorm.route("/")
class AudioNormalizeResource(Resource):
    @ns_anorm.expect(parser)
    @ns_anorm.doc(description="Normalize loudness to target LUFS while preserving video (if any).")
    def post(self):
        args = parser.parse_args()
        f = args.get("media")
        if not f:
            return {"message": "No media provided"}, 400

        try:
            t_i  = float(request.values.get("target_i",  -14.0))
        except ValueError:
            t_i = -14.0
        try:
            t_tp = float(request.values.get("target_tp", -1.5))
        except ValueError:
            t_tp = -1.5
        try:
            t_lra = float(request.values.get("target_lra", 11.0))
        except ValueError:
            t_lra = 11.0

        audio_output = request.values.get("audio_output")  # mp3|wav|m4a (only for audio inputs)
        aac_bitrate  = request.values.get("aac_bitrate", "192k")  # for video inputs

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("NORMALIZE_OUTPUT", "normalize_output")

            path = AudioNormalizeService.save_upload(f, upload_dir=upload_dir)
            svc = AudioNormalizeService(path, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                target_i=t_i, target_tp=t_tp, target_lra=t_lra,
                audio_output=audio_output, aac_bitrate=aac_bitrate
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
