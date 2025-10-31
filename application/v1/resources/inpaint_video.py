from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
from application.v1.services.inpaint_video_service import InpaintVideoService

ns_video_inpaint = Namespace(
    "VideoInpaint",
    path="/inpaint/",
    description="Video text/watermark removal using OCR + LaMa."
)

parser = ns_video_inpaint.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video (mp4/mov/mkv/webm)")
parser.add_argument("ocr_langs", location="form", required=False, help="OCR langs, e.g. 'en,ja' (default 'en')")
parser.add_argument("bbox_pad", location="form", required=False, help="Pad OCR boxes (px, default 8)")
parser.add_argument("smooth", location="form", required=False, help="Temporal smoothing radius (frames, default 1)")
parser.add_argument("static_thresh", location="form", required=False, help="Static logo threshold 0..1 (default 0.25)")
parser.add_argument("device", location="form", required=False, help="cpu|cuda (default cpu)")


@ns_video_inpaint.route("/video")
class VideoInpaintResource(Resource):
    @ns_video_inpaint.expect(parser)
    @ns_video_inpaint.doc(description="Upload a video; removes text/watermarks using OCR + LaMa, preserves audio.")
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video uploaded"}, 400

        ocr_langs = request.values.get("ocr_langs", "en")
        device = request.values.get("device", "cpu")
        try:
            bbox_pad = int(request.values.get("bbox_pad", 8))
        except ValueError:
            bbox_pad = 8
        try:
            smooth = int(request.values.get("smooth", 1))
        except ValueError:
            smooth = 1
        try:
            static_thresh = float(request.values.get("static_thresh", 0.25))
        except ValueError:
            static_thresh = 0.25

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("INPAINT_OUTPUT", "inpaint_output")

            vpath = InpaintVideoService.save_upload(f, upload_dir=upload_dir)
            svc = InpaintVideoService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                ocr_langs=ocr_langs,
                bbox_pad=bbox_pad,
                device=device,
                smooth=smooth,
                static_thresh=static_thresh
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
