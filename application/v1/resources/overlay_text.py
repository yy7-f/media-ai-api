from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
from application.v1.services.overlay_text_service import OverlayTextService
import os
from application.workers import api_key_required

ns_overlay = Namespace(
    "Overlay",
    path="/overlay/",
    description="Burn arbitrary text onto video using FFmpeg drawtext."
)

parser = ns_overlay.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video file")
parser.add_argument("text",  location="form", required=True, help="Text to overlay")
parser.add_argument("x",     location="form", required=False, help="X expr (default center)")
parser.add_argument("y",     location="form", required=False, help="Y expr (default bottom)")
parser.add_argument("start", location="form", required=False, help="Start sec (optional)")
parser.add_argument("end",   location="form", required=False, help="End sec (optional)")
parser.add_argument("fontsize",   location="form", required=False, help="Font size (default 42)")
parser.add_argument("fontcolor",  location="form", required=False, help="Font color (default white)")
parser.add_argument("box",        location="form", required=False, help="1|0 (default 1)")
parser.add_argument("boxcolor",   location="form", required=False, help="RGBA eg black@0.5")
parser.add_argument("boxborderw", location="form", required=False, help="Box border (default 10)")
parser.add_argument("fontfile",   location="form", required=False, help="Absolute font path")

@ns_overlay.route("/text")
class OverlayTextResource(Resource):
    @ns_overlay.expect(parser)
    @ns_overlay.doc(description="Upload a video + text and get an MP4 with burned overlay text.",
                    security="apikey",  # Swagger uses your API-KEY scheme
                    )
    @api_key_required  # ✅ enforce header
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        text = request.values.get("text")
        if not f or not text:
            return {"message": "video and text are required"}, 400

        x = request.values.get("x") or "(w-text_w)/2"
        y = request.values.get("y") or "h-100"
        start = request.values.get("start")
        end   = request.values.get("end")
        start = float(start) if start is not None and start != "" else None
        end   = float(end)   if end   is not None and end   != "" else None

        try:
            fontsize   = int(request.values.get("fontsize", 42))
        except ValueError:
            fontsize = 42
        fontcolor  = request.values.get("fontcolor", "white")
        try:
            box       = int(request.values.get("box", 1))
        except ValueError:
            box = 1
        boxcolor   = request.values.get("boxcolor", "black@0.5")
        try:
            boxborderw= int(request.values.get("boxborderw", 10))
        except ValueError:
            boxborderw = 10
        fontfile   = request.values.get("fontfile")  # optional

        try:
            upload_dir = current_app.config.get("UPLOAD_FOLDER", "/tmp/uploads")
            output_root = current_app.config.get("OVERLAY_OUTPUT", "/tmp/overlay_output")
            bucket_name = current_app.config.get("OUTPUT_BUCKET", "media-ai-api-output")
            bucket_name = "media-ai-api-output"

            vpath = OverlayTextService.save_upload(f, upload_dir)
            svc = OverlayTextService(vpath, work_root=upload_dir, output_root=output_root)

            res = svc.process(
                text=text, x=x, y=y, start=start, end=end,
                fontsize=fontsize, fontcolor=fontcolor,
                box=box, boxcolor=boxcolor, boxborderw=boxborderw,
                fontfile=fontfile,
                bucket_name=bucket_name
            )
            return jsonify({
                "status": "ok",
                "result_path": res.output_path,  # internal /tmp path
                "filename": os.path.basename(res.output_path),
                "gcs_url": res.diagnostics.get("gcs_url"),  # 👈 public-ish location
                "diagnostics": res.diagnostics,
            })
        except Exception as e:
            return {"message": f"Unexpected error: {e}"}, 500
