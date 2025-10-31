import uuid, time, threading
from concurrent.futures import ThreadPoolExecutor

class JobStatus:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE    = "DONE"
    ERROR   = "ERROR"
    CANCELED= "CANCELED"

class JobManager:
    def __init__(self, max_workers=2):
        self.exec = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs = {}        # job_id -> dict
        self._lock = threading.Lock()

    def _new_job(self, kind: str):
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "kind": kind,
                "status": JobStatus.PENDING,
                "progress": 0,
                "result_path": None,
                "diagnostics": {},
                "error": None,
                "created_at": int(time.time())
            }
        return job_id

    def set_progress(self, job_id: str, pct: int, **diag):
        with self._lock:
            if job_id in self._jobs and self._jobs[job_id]["status"] not in (JobStatus.DONE, JobStatus.ERROR, JobStatus.CANCELED):
                self._jobs[job_id]["progress"] = max(0, min(100, int(pct)))
                if diag:
                    self._jobs[job_id]["diagnostics"].update(diag)

    def set_result(self, job_id: str, path: str, diagnostics: dict):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = JobStatus.DONE
                self._jobs[job_id]["progress"] = 100
                self._jobs[job_id]["result_path"] = path
                if diagnostics:
                    self._jobs[job_id]["diagnostics"].update(diagnostics)

    def set_error(self, job_id: str, msg: str):
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = JobStatus.ERROR
                self._jobs[job_id]["error"] = msg

    def cancel(self, job_id: str):
        with self._lock:
            if job_id in self._jobs and self._jobs[job_id]["status"] not in (JobStatus.DONE, JobStatus.ERROR):
                self._jobs[job_id]["status"] = JobStatus.CANCELED

    def get(self, job_id: str):
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit=50):
        with self._lock:
            items = list(self._jobs.values())
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return items[:limit]

JOB_MANAGER = JobManager(max_workers=2)
