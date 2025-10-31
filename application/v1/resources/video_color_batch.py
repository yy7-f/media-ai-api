from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
from typing import List

from application.v1.services.video_color_batch_service import VideoColorBatchService

ns_color_batch = Namespace(
    "VideoColorBatch",
    path="/video/effects/color/batch/",
    description="Apply the same color grade or LUT to multiple clips. Optional resize."
)

parser = ns_color_batch.parser()
parser.add_argument("clips", location="files", type=FileStorage, required=True, action="append",
                    help="Upload 1+ video files under the field name 'clips'")
parser.add_argument("mode", location="form", required=False,
                    help="grayscale|sepia|bw_highcontrast|cinematic|brightness|contrast|saturation|lut (default cinematic)")
parser.add_argument("value", location="form", required=False, help="Numeric value for brightness/contrast/saturation")
parser.add_argument("lut_path", location="form", required=False, help="Path to LUT .cube (mode=lut)")
parser.add_argument("crf", location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset", location="form", required=False, help="x264 preset (default veryfast)")
parser.add_argument("copy_audio", location="form", required=False, help="true|false (default true)")
parser.add_argument("zip", location="form", required=False, help="true|false (default false)")
parser.add_argument("target_resolution", location="form", required=False,
                    help="Output resolution WIDTHxHEIGHT (e.g., 1920x1080 or 1080x1920)")

@ns_color_batch.route("/")
class VideoColorBatchResource(Resource):
    @ns_color_batch.expect(parser)
    @ns_color_batch.doc(description="Grades multiple videos with the same color filter/LUT, with optional resizing and zip bundling.")
    def post(self):
        args = parser.parse_args()
        files = args.get("clips")
        if not files:
            return {"message": "Upload at least one clip under 'clips'."}, 400
        if not isinstance(files, list):
            files = [files]

        def to_float(v):
            try: return float(v) if v not in (None, "") else None
            except Exception: return None
        def to_int(v, d):
            try: return int(v) if v not in (None, "") else d
            except Exception: return d
        def to_bool(v, d):
            if v is None: return d
            return str(v).lower() == "true"

        mode       = request.values.get("mode", "cinematic")
        value      = to_float(request.values.get("value"))
        lut_path   = request.values.get("lut_path")
        crf        = to_int(request.values.get("crf"), 18)
        preset     = request.values.get("preset", "veryfast")
        copy_audio = to_bool(request.values.get("copy_audio"), True)
        make_zip   = to_bool(request.values.get("zip"), False)
        target_res = request.values.get("target_resolution")

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("COLOR_OUTPUT", "color_output")

            paths = VideoColorBatchService.save_uploads(files, upload_dir=upload_dir)
            svc = VideoColorBatchService(paths, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                mode=mode, value=value, lut_path=lut_path,
                crf=crf, preset=preset, copy_audio=copy_audio,
                make_zip=make_zip, target_resolution=target_res
            )

            return jsonify({
                "status": "ok",
                "zip_path": res.zipped_path,
                "outputs": [
                    {
                        "input": it.input_path,
                        "output": it.output_path,
                        "ok": it.ok,
                        "error": it.error,
                        "filter": it.filter_used
                    } for it in res.outputs
                ],
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
