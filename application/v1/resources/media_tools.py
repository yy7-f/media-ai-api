from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.transcription_service import TranscriptionService
from application.v1.services.captions_service import CaptionsService
from application.v1.services.overlay_service import OverlayService

ns_media = Namespace(
    "MediaTools",
    path="/media/",
    description="Transcription, captions burn-in, and overlay text tools."
)

# ---------- /transcribe ----------
transcribe_parser = ns_media.parser()
transcribe_parser.add_argument("file", location="files", type=FileStorage, required=True, help="Video/Audio file")
transcribe_parser.add_argument("lang", location="form", required=False, help="Optional language hint (e.g., 'en')")

@ns_media.route("/transcribe")
class TranscribeResource(Resource):
    @ns_media.expect(transcribe_parser)
    @ns_media.doc(description="Transcribe media to JSON + SRT + VTT")
    def post(self):
        args = transcribe_parser.parse_args()
        f = args.get("file")
        lang = request.values.get("lang")

        if not f:
            return {"message": "No file provided"}, 400

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("TRANSCRIBE_OUTPUT", "transcribe_output")

            saved = TranscriptionService.save_upload(f, upload_dir=upload_dir)
            svc = TranscriptionService(saved, work_root=upload_dir, output_root=output_root)

            # ---- ASR backend (hosted API stub) ----
            def asr_backend(audio_path, lang_hint):
                # Replace this stub with your hosted ASR call.
                # It must return [{"start": float, "end": float, "text": str}, ...]
                # For now, raise to force integration.
                raise RuntimeError("ASR backend not configured. Wire your API here.")

            result = svc.process(asr_backend, lang=lang)
            svc.cleanup()

            return jsonify({
                "status": "ok",
                "json": result.transcript_json_path,
                "srt": result.srt_path,
                "vtt": result.vtt_path,
                "diagnostics": result.diagnostics
            })
        except Exception as e:
            return {"message": str(e)}, 500

# ---------- /captions/burn ----------
burn_parser = ns_media.parser()
burn_parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video file")
burn_parser.add_argument("srt",   location="files", type=FileStorage, required=True, help="SRT subtitles file")
burn_parser.add_argument("fontsize", location="form", required=False, help="Font size (default 24)")
burn_parser.add_argument("border",   location="form", required=False, help="Outline width (default 3)")

@ns_media.route("/captions/burn")
class BurnCaptionsResource(Resource):
    @ns_media.expect(burn_parser)
    @ns_media.doc(description="Burn SRT captions into a video")
    def post(self):
        args = burn_parser.parse_args()
        v_file = args.get("video")
        s_file = args.get("srt")
        if not v_file or not s_file:
            return {"message": "Both video and srt are required"}, 400

        fontsize = int(request.values.get("fontsize", 24))
        border   = int(request.values.get("border", 3))

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("CAPTIONS_OUTPUT", "captions_output")

            v_path = CaptionsService.save_video(v_file, upload_dir=upload_dir)
            s_path = CaptionsService.save_srt(s_file, upload_dir=upload_dir)

            svc = CaptionsService(v_path, s_path, output_root=output_root)
            res = svc.burn(fontsize=fontsize, border=border)

            return jsonify({
                "status": "ok",
                "result_path": res.output_path,
                "filename": res.output_path.split("/")[-1],
                "diagnostics": res.diagnostics
            })
        except Exception as e:
            return {"message": str(e)}, 500

# ---------- /overlay/text ----------
overlay_parser = ns_media.parser()
overlay_parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video file")
overlay_parser.add_argument("blocks", location="form", required=True, help="JSON array of overlay blocks")

@ns_media.route("/overlay/text")
class OverlayTextResource(Resource):
    @ns_media.expect(overlay_parser)
    @ns_media.doc(
        description="Overlay timed text on video. blocks=[{text,start,end,x?,y?,fontfile?,fontsize?,color?,box?,boxcolor?},...]"
    )
    def post(self):
        args = overlay_parser.parse_args()
        v_file = args.get("video")
        blocks_raw = args.get("blocks")
        if not v_file or not blocks_raw:
            return {"message": "video and blocks are required"}, 400

        try:
            blocks = json.loads(blocks_raw)
            if not isinstance(blocks, list):
                return {"message": "blocks must be a JSON array"}, 400

            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("OVERLAY_OUTPUT", "overlay_output")

            # Save video
            from application.v1.services.captions_service import CaptionsService
            v_path = CaptionsService.save_video(v_file, upload_dir=upload_dir)

            svc = OverlayService(v_path, output_root=output_root)
            res = svc.render(blocks)

            return jsonify({
                "status": "ok",
                "result_path": res.output_path,
                "filename": res.output_path.split("/")[-1],
                "diagnostics": res.diagnostics
            })
        except Exception as e:
            return {"message": str(e)}, 500
