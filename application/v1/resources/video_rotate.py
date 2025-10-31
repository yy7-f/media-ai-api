from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
from application.v1.services.video_rotate_service import VideoRotateService

ns_rotate = Namespace("VideoRotate", path="/video/rotate/", description="Rotate video 90/180/270 degrees")

parser = ns_rotate.parser()
parser.add_argument("video", location="files", type=FileStorage, required=True)
parser.add_argument("degrees", location="form", required=False, help="0|90|180|270 (default 90)")
parser.add_argument("metadata_only", location="form", required=False, help="true|false (default false)")
parser.add_argument("crf", location="form", required=False, help="x264 CRF (default 18)")
parser.add_argument("preset", location="form", required=False, help="x264 preset (default veryfast)")
parser.add_argument("copy_audio", location="form", required=False, help="true|false (default true)")

@ns_rotate.route("/")
class VideoRotateResource(Resource):
    @ns_rotate.expect(parser)
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f: return {"message": "No video provided"}, 400

        def to_int(v,d):
            try: return int(v) if v not in (None,"") else d
            except ValueError: return d
        def to_bool(v,d):
            if v is None: return d
            return str(v).lower() == "true"

        degrees = to_int(request.values.get("degrees"), 90)
        metadata_only = to_bool(request.values.get("metadata_only"), False)
        crf = to_int(request.values.get("crf"), 18)
        preset = request.values.get("preset", "veryfast")
        copy_audio = to_bool(request.values.get("copy_audio"), True)

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("ROTATE_OUTPUT", "rotate_output")

            vpath = VideoRotateService.save_upload(f, upload_dir=upload_dir)
            svc = VideoRotateService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(degrees=degrees, metadata_only=metadata_only, crf=crf, preset=preset, copy_audio=copy_audio)

            return jsonify({"status":"ok","result_path": res.output_path,"filename": res.output_path.split("/")[-1],"diagnostics": res.diagnostics})
        except Exception as e:
            return {"message": f"Unexpected error: {e}"}, 500
