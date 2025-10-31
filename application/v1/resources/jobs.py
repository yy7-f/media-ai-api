from flask import request, jsonify, current_app
from flask_restx import Namespace, Resource
from werkzeug.datastructures import FileStorage

from application.jobs import JOB_MANAGER
from application.v1.services.inpaint_video_service import InpaintVideoService

ns_jobs = Namespace("Jobs", path="/jobs/", description="Background job runner")

# Start a video inpaint job
start_parser = ns_jobs.parser()
start_parser.add_argument("video", location="files", type=FileStorage, required=True, help="Video file")
start_parser.add_argument("ocr_langs", location="form", required=False)
start_parser.add_argument("bbox_pad", location="form", required=False)
start_parser.add_argument("smooth", location="form", required=False)
start_parser.add_argument("static_thresh", location="form", required=False)
start_parser.add_argument("device", location="form", required=False)

@ns_jobs.route("/inpaint/video")
class StartVideoInpaintJob(Resource):
    @ns_jobs.expect(start_parser)
    def post(self):
        args = start_parser.parse_args()
        f = args.get("video")
        if not f:
            return {"message": "No video provided"}, 400

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

        upload_dir  = current_app.config.get("UPLOAD_FOLDER", "uploads")
        output_root = current_app.config.get("INPAINT_OUTPUT", "inpaint_output")

        # save upload now so the worker can access it
        vpath = InpaintVideoService.save_upload(f, upload_dir=upload_dir)

        job_id = JOB_MANAGER._new_job("video_inpaint")

        def runner():
            try:
                svc = InpaintVideoService(vpath, work_root=upload_dir, output_root=output_root)
                res = svc.process(
                    ocr_langs=ocr_langs,
                    bbox_pad=bbox_pad,
                    device=device,
                    smooth=smooth,
                    static_thresh=static_thresh,
                    progress_cb=lambda p, **d: JOB_MANAGER.set_progress(job_id, p, **d)
                )
                svc.cleanup()
                JOB_MANAGER.set_result(job_id, res.output_path, res.diagnostics)
            except Exception as e:
                JOB_MANAGER.set_error(job_id, str(e))

        # submit to thread pool
        JOB_MANAGER.set_progress(job_id, 1, phase="queued")
        JOB_MANAGER.exec.submit(runner)
        # flip to running immediately (optional)
        JOB_MANAGER.set_progress(job_id, 2, phase="started")
        with JOB_MANAGER._lock:
            JOB_MANAGER._jobs[job_id]["status"] = "RUNNING"

        return jsonify({"job_id": job_id, "status": "RUNNING", "progress": 2})

# Get job status
@ns_jobs.route("/<string:job_id>")
class JobStatusResource(Resource):
    def get(self, job_id):
        job = JOB_MANAGER.get(job_id)
        if not job:
            return {"message": "Job not found"}, 404
        return jsonify(job)

# Cancel job (best-effort)
@ns_jobs.route("/<string:job_id>/cancel")
class JobCancelResource(Resource):
    def post(self, job_id):
        job = JOB_MANAGER.get(job_id)
        if not job:
            return {"message": "Job not found"}, 404
        JOB_MANAGER.cancel(job_id)
        return jsonify({"status": "CANCELED"})
