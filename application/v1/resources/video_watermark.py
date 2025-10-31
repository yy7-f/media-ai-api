from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.video_watermark_service import VideoWatermarkService

ns_wm = Namespace(
    "VideoWatermark",
    path="/video/watermark/",
    description="Overlay an image watermark with position, opacity, scale, and timing."
)

parser = ns_wm.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video file")
parser.add_argument("image", location="files", type=FileStorage, required=True, help="Watermark image (png/jpg/webp/gif)")
parser.add_argument("position",  location="form", required=False, help="top-left|top-right|bottom-left|bottom-right|center (default bottom-right)")
parser.add_argument("margin_x",  location="form", required=False, help="X margin in px (default 24)")
parser.add_argument("margin_y",  location="form", required=False, help="Y margin in px (default 24)")
parser.add_argument("opacity",   location="form", required=False, help="0..1 (default 0.85)")
parser.add_argument("scale_pct", location="form", required=False, help="Scale watermark relative to its original size in % (default 20)")
parser.add_argument("t_start",   location="form", required=False, help="Show watermark starting at t (sec)")
parser.add_argument("t_end",     location="form", required=False, help="Hide after t (sec)")
parser.add_argument("crf",       location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset",    location="form", required=False, help="x264 preset (default veryfast)")
parser.add_argument("copy_audio",location="form", required=False, help="true|false (default true)")

@ns_wm.route("/")
class VideoWatermarkResource(Resource):
    @ns_wm.expect(parser)
    @ns_wm.doc(description="Burn a watermark image onto the uploaded video.")
    def post(self):
        args = parser.parse_args()
        f_vid = args.get("video")
        f_img = args.get("image")
        if not f_vid or not f_img:
            return {"message": "Provide both 'video' and 'image' files."}, 400

        def to_int(v, d):
            try: return int(v) if v not in (None, "") else d
            except ValueError: return d
        def to_float(v, d):
            try: return float(v) if v not in (None, "") else d
            except ValueError: return d
        def to_bool(v, d):
            if v is None: return d
            return str(v).lower() == "true"

        position  = request.values.get("position", "bottom-right")
        margin_x  = to_int(request.values.get("margin_x"), 24)
        margin_y  = to_int(request.values.get("margin_y"), 24)
        opacity   = to_float(request.values.get("opacity"), 0.85)
        scale_pct = to_float(request.values.get("scale_pct"), 20.0)

        t_start   = request.values.get("t_start")
        t_end     = request.values.get("t_end")
        t_start_f = to_float(t_start, None) if t_start not in (None, "") else None
        t_end_f   = to_float(t_end, None)   if t_end   not in (None, "") else None

        crf       = to_int(request.values.get("crf"), 18)
        preset    = request.values.get("preset", "veryfast")
        copy_audio= to_bool(request.values.get("copy_audio"), True)

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("WATERMARK_OUTPUT", "watermark_output")

            vpath = VideoWatermarkService.save_upload(f_vid, upload_dir, VideoWatermarkService.ALLOWED_VIDEO)
            ipath = VideoWatermarkService.save_upload(f_img, upload_dir, VideoWatermarkService.ALLOWED_IMAGE)

            svc = VideoWatermarkService(vpath, ipath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                position=position, margin_x=margin_x, margin_y=margin_y,
                opacity=opacity, scale_pct=scale_pct,
                t_start=t_start_f, t_end=t_end_f,
                crf=crf, preset=preset, copy_audio=copy_audio
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
