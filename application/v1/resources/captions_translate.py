from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.captions_translate_service import CaptionsTranslateService

ns_ctran = Namespace(
    "CaptionsTranslate",
    path="/captions/translate/",
    description="Offline caption translation using Argos Translate."
)

parser = ns_ctran.parser()
parser.add_argument("captions", location="files", type=FileStorage, required=True,
                    help="SRT / VTT / JSON({segments:[{start,end,text}]})")
parser.add_argument("target_lang", location="form", required=True, help="Target language code, e.g. en, ja, es")
parser.add_argument("source_lang", location="form", required=False, help="Source language code (optional)")
parser.add_argument("emit_srt",   location="form", required=False, help="true|false (default true)")
parser.add_argument("emit_vtt",   location="form", required=False, help="true|false (default true)")

@ns_ctran.route("/")
class CaptionsTranslateResource(Resource):
    @ns_ctran.expect(parser)
    @ns_ctran.doc(description="Translate captions file to target language; returns JSON and optional SRT/VTT.")
    def post(self):
        args = parser.parse_args()
        f = args.get("captions")
        if not f:
            return {"message": "No captions file provided"}, 400

        target_lang = request.values.get("target_lang")
        if not target_lang:
            return {"message": "target_lang is required (e.g., en, ja, es)"}, 400

        source_lang = request.values.get("source_lang")
        emit_srt = str(request.values.get("emit_srt", "true")).lower() == "true"
        emit_vtt = str(request.values.get("emit_vtt", "true")).lower() == "true"

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("CAPTIONS_OUTPUT", "captions_output")

            path = CaptionsTranslateService.save_upload(f, upload_dir=upload_dir)
            svc = CaptionsTranslateService(path, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                target_lang=target_lang.strip().lower(),
                source_lang=(source_lang.strip().lower() if source_lang else None),
                emit_srt=emit_srt,
                emit_vtt=emit_vtt
            )

            return jsonify({
                "status": "ok",
                "json": res.out_json,
                "srt": res.out_srt,
                "vtt": res.out_vtt,
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
