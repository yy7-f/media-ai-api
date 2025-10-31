from flask import current_app, request, jsonify
from flask_restx import Resource, Namespace
from werkzeug.datastructures import FileStorage

from application.v1.services.audio_mix_service import AudioMixService

ns_amix = Namespace(
    "AudioMix",
    path="/audio/mix/",
    description="Mix main (video/audio) with background music; optional auto-ducking."
)

parser = ns_amix.parser()
parser.add_argument("main", location="files", type=FileStorage, required=True,
                    help="Main media (video or audio)")
parser.add_argument("bgm",  location="files", type=FileStorage, required=True,
                    help="Background music (audio)")
parser.add_argument("bgm_db", location="form", required=False, help="Initial BGM gain dB (default -12)")
parser.add_argument("ducking", location="form", required=False, help="true|false (default true)")
parser.add_argument("duck_threshold_db", location="form", required=False, help="Sidechain threshold dB (default -30)")
parser.add_argument("duck_ratio", location="form", required=False, help="Compression ratio (default 8)")
parser.add_argument("duck_attack_ms", location="form", required=False, help="Attack ms (default 10)")
parser.add_argument("duck_release_ms", location="form", required=False, help="Release ms (default 250)")
parser.add_argument("bgm_offset_s", location="form", required=False, help="BGM start offset seconds (default 0)")
parser.add_argument("loop_bgm", location="form", required=False, help="Loop BGM to full length (default true)")
parser.add_argument("master_db", location="form", required=False, help="Final master gain dB (default 0)")
parser.add_argument("aac_bitrate", location="form", required=False, help="If video output: AAC bitrate (default 192k)")

@ns_amix.route("/")
class AudioMixResource(Resource):
    @ns_amix.expect(parser)
    @ns_amix.doc(description="Upload main + bgm; returns mixed media (video keeps video stream, audio-only outputs MP3).")
    def post(self):
        args = parser.parse_args()
        f_main = args.get("main")
        f_bgm  = args.get("bgm")
        if not f_main or not f_bgm:
            return {"message": "Provide both 'main' and 'bgm' files."}, 400

        def to_float(v, dflt):
            try:
                return float(v) if v not in (None, "") else dflt
            except ValueError:
                return dflt

        def to_int(v, dflt):
            try:
                return int(v) if v not in (None, "") else dflt
            except ValueError:
                return dflt

        bgm_db = to_float(request.values.get("bgm_db"), -12.0)
        ducking = (request.values.get("ducking", "true").lower() == "true")
        duck_threshold_db = to_float(request.values.get("duck_threshold_db"), -30.0)
        duck_ratio = to_float(request.values.get("duck_ratio"), 8.0)
        duck_attack_ms = to_int(request.values.get("duck_attack_ms"), 10)
        duck_release_ms = to_int(request.values.get("duck_release_ms"), 250)
        bgm_offset_s = to_float(request.values.get("bgm_offset_s"), 0.0)
        loop_bgm = (request.values.get("loop_bgm", "true").lower() == "true")
        master_db = to_float(request.values.get("master_db"), 0.0)
        aac_bitrate = request.values.get("aac_bitrate", "192k")

        try:
            upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
            output_root = current_app.config.get("MIX_OUTPUT", "mix_output")

            main_path = AudioMixService.save_upload(f_main, upload_dir, AudioMixService.ALLOWED_MAIN)
            bgm_path  = AudioMixService.save_upload(f_bgm, upload_dir, AudioMixService.ALLOWED_BGM)

            svc = AudioMixService(main_path, bgm_path, work_root=upload_dir, output_root=output_root)
            res = svc.process(
                bgm_db=bgm_db, ducking=ducking,
                duck_threshold_db=duck_threshold_db, duck_ratio=duck_ratio,
                duck_attack_ms=duck_attack_ms, duck_release_ms=duck_release_ms,
                bgm_offset_s=bgm_offset_s, loop_bgm=loop_bgm,
                master_db=master_db, aac_bitrate=aac_bitrate
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
