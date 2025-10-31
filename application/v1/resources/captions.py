from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
from application.v1.services.captions_burn_service import CaptionsBurnService

ns_captions = Namespace(
    "Captions",
    path="/captions/",
    description="Burn SRT/VTT subtitles into video (hard subs)."
)

parser = ns_captions.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video (mp4/mov/mkv/webm)")
parser.add_argument("subs",  location="files", type=FileStorage, required=True, help="Subtitles (srt or vtt)")
parser.add_argument("fontsize", location="form", required=False, help="Font size (default 28)")
parser.add_argument("primary_hex", location="form", required=False, help="Text color hex RRGGBB (default FFFFFF)")
parser.add_argument("outline_hex", location="form", required=False, help="Outline color hex RRGGBB (default 000000)")
parser.add_argument("outline", location="form", required=False, help="Outline width (default 2)")
parser.add_argument("y_margin", location="form", required=False, help="Bottom margin px (default 24)")

@ns_captions.route("/burn")
class CaptionsBurnResource(Resource):
    @ns_captions.expect(parser)
    @ns_captions.doc(description="Upload a video + SRT/VTT; returns path to an MP4 with hard-burned captions.")
    def post(self):
        args = parser.parse_args()
        f_video = args.get("video")
        f_subs  = args.get("subs")
        if not f_video or not f_subs:
            return {"message": "Both video and subs are required"}, 400

        try:
            fontsize = int(request.values.get("fontsize", 28))
        except ValueError:
            fontsize = 28
        primary_hex = (request.values.get("primary_hex") or "FFFFFF").upper()
        outline_hex = (request.values.get("outline_hex") or "000000").upper()
        try:
            outline = int(request.values.get("outline", 2))
        except ValueError:
            outline = 2
        try:
            y_margin = int(request.values.get("y_margin", 24))
        except ValueError:
            y_margin = 24

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("OVERLAY_OUTPUT", "overlay_output")

            vpath = CaptionsBurnService.save_upload(f_video, upload_dir, CaptionsBurnService.ALLOWED_VIDEO)
            spath = CaptionsBurnService.save_upload(f_subs, upload_dir, CaptionsBurnService.ALLOWED_SUBS)

            svc = CaptionsBurnService(vpath, spath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                fontsize=fontsize,
                primary_hex=primary_hex,
                outline_hex=outline_hex,
                outline=outline,
                y_margin=y_margin
            )
            return jsonify({
                "status": "ok",
                "result_path": res.output_path,
                "filename": res.output_path.split("/")[-1],
                "diagnostics": res.diagnostics
            })
        except Exception as e:
            return {"message": f"Unexpected error: {e}"}, 500
