import os
from google.cloud import storage

def upload_to_gcs(local_path: str, bucket_name: str, dest_path: str) -> str:
    """Uploads a local file to GCS and returns the public URL."""
    if not os.path.isfile(local_path):
        raise FileNotFoundError(local_path)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_path)

    blob.upload_from_filename(local_path)
    return f"https://storage.googleapis.com/{bucket_name}/{dest_path}"