from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
from application.v1.services.video_speed_service import VideoSpeedService

ns_speed = Namespace("VideoSpeed", path="/video/speed/", description="Change playback speed for video+audio")

parser = ns_speed.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True)
parser.add_argument("factor", location="form", required=False, help=">0, e.g. 0.75 (slower), 1.25 (faster)")
parser.add_argument("crf", location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset", location="form", required=False, help="x264 preset (default veryfast)")

@ns_speed.route("/")
class VideoSpeedResource(Resource):
    @ns_speed.expect(parser)
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f: return {"message": "No video provided"}, 400

        def to_float(v,d):
            try: return float(v) if v not in (None,"") else d
            except ValueError: return d
        def to_int(v,d):
            try: return int(v) if v not in (None,"") else d
            except ValueError: return d

        factor = to_float(request.values.get("factor"), 1.25)
        crf = to_int(request.values.get("crf"), 18)
        preset = request.values.get("preset", "veryfast")

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("SPEED_OUTPUT", "speed_output")

            vpath = VideoSpeedService.save_upload(f, upload_dir=upload_dir)
            svc = VideoSpeedService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(factor=factor, crf=crf, preset=preset)

            return jsonify({"status":"ok","result_path": res.output_path,"filename": res.output_path.split("/")[-1],"diagnostics": res.diagnostics})
        except Exception as e:
            return {"message": f"Unexpected error: {e}"}, 500
