from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.transcribe_fw_service import TranscribeFWService

ns_transcribe = Namespace(
    "Transcribe",
    path="/transcribe/",
    description="Local CPU transcription using faster-whisper (no GPU required)."
)

parser = ns_transcribe.parser()
parser.add_argument("media", location="files", type=FileStorage, required=True,
                    help="Audio/Video file (mp3/mp4/mov/mkv/wav/ogg...)")
parser.add_argument("model_size", location="form", required=False,
                    help="tiny|base|small|medium|large-v3 (default base)")
parser.add_argument("lang", location="form", required=False,
                    help="Language hint, e.g., en, ja (optional)")


@ns_transcribe.route("/")
class TranscribeResource(Resource):
    @ns_transcribe.expect(parser)
    @ns_transcribe.doc(description="Synchronous transcription; returns JSON/SRT/VTT file paths.")
    def post(self):
        args = parser.parse_args()
        f = args.get("media")
        if not f:
            return {"message": "No media provided"}, 400

        model_size = request.values.get("model_size", "base")
        lang = request.values.get("lang") or None

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("TRANSCRIBE_OUTPUT", "transcribe_output")

            media_path = TranscribeFWService.save_upload(f, upload_dir=upload_dir)
            svc = TranscribeFWService(media_path, work_root=upload_dir, output_root=output_root)
            res = svc.process(model_size=model_size, language=lang)
            svc.cleanup()

            return jsonify({
                "status": "ok",
                "json": res.json_path,
                "srt": res.srt_path,
                "vtt": res.vtt_path,
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
