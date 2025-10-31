from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage
import json

from application.v1.services.shuffle_video_service import ShuffleVideoService

ns_shuffle = Namespace(
    "ShuffleVideo",
    path="/shuffle/",
    description="Shuffle video segments easily with FFmpeg."
)

parser = ns_shuffle.parser()
parser.add_argument("video",     location="files", type=FileStorage, required=True, help="Video file (mp4/mov/mkv/webm)")
parser.add_argument("segments",  location="form", required=False, help="JSON list of [start,end] seconds")
parser.add_argument("chunk_sec", location="form", required=False, help="Auto-split chunk length in seconds")
parser.add_argument("seed",      location="form", required=False, help="Random seed (int)")
parser.add_argument("reencode",  location="form", required=False, help="true|false (default true)")
parser.add_argument("copy_audio",location="form", required=False, help="true|false (default true)")


@ns_shuffle.route("/")
class ShuffleVideoResource(Resource):
    @ns_shuffle.expect(parser)
    @ns_shuffle.doc(description="Upload a video and either provide 'segments' or 'chunk_sec' to shuffle video segments.")
    def post(self):
        args = parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video provided"}, 400

        segments_raw = request.values.get("segments")
        chunk_sec = request.values.get("chunk_sec")
        seed = request.values.get("seed")
        reencode = (request.values.get("reencode", "true").lower() == "true")
        copy_audio = (request.values.get("copy_audio", "true").lower() == "true")

        segments = None
        if segments_raw:
            try:
                segments = json.loads(segments_raw)
                if not isinstance(segments, list) or not all(isinstance(x, (list, tuple)) and len(x) == 2 for x in segments):
                    return {"message": "segments must be JSON like [[0,5],[12.3,18.7],...]"}, 400
            except Exception:
                return {"message": "Invalid JSON for segments"}, 400

        if not segments and not chunk_sec:
            return {"message": "Provide either 'segments' or 'chunk_sec'"}, 400

        try:
            if chunk_sec:
                chunk_sec = float(chunk_sec)
                if chunk_sec <= 0:
                    return {"message": "chunk_sec must be > 0"}, 400
            seed = int(seed) if seed not in (None, "",) else None
        except ValueError:
            return {"message": "Invalid numeric value for chunk_sec or seed"}, 400

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("SHUFFLED_OUTPUT", "shuffled_output")

            vpath = ShuffleVideoService.save_upload(f, upload_dir=upload_dir)
            svc = ShuffleVideoService(vpath, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                segments=segments,
                chunk_sec=chunk_sec,
                seed=seed,
                reencode=reencode,
                copy_audio=copy_audio
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
