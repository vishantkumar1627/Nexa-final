import os
import shutil
import boto3
from pathlib import Path
from typing import Optional
from botocore.exceptions import NoCredentialsError
from shared.config import settings


class StorageService:
    """
    Unified file storage service.
    Priority: Supabase Storage → AWS S3 → Local filesystem.
    """

    def __init__(self):
        self.base_dir = Path(settings.STORAGE_DIR)
        # Ensure all folders exist locally (used as a write-through cache)
        self.floorplan_dir = self.base_dir / "floorplans"
        self.model3d_dir = self.base_dir / "models3d"
        self.render_dir = self.base_dir / "renders"
        os.makedirs(self.floorplan_dir, exist_ok=True)
        os.makedirs(self.model3d_dir, exist_ok=True)
        os.makedirs(self.render_dir, exist_ok=True)

        # Initialize Supabase client if configured
        self.supabase = None
        if settings.USE_SUPABASE and settings.SUPABASE_URL:
            try:
                # Fast DNS and socket check to avoid long sequential upload timeouts in offline environments
                import socket
                from urllib.parse import urlparse
                parsed_url = urlparse(settings.SUPABASE_URL)
                hostname = parsed_url.hostname or "supabase.co"
                
                # Check socket with a 1.0 second timeout limit
                socket.setdefaulttimeout(1.0)
                socket.gethostbyname(hostname)
                
                from supabase import create_client
                self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
                print(f"[Storage] Supabase client initialised -> bucket: {settings.SUPABASE_BUCKET}")
            except Exception as e:
                print(f"[Storage] Supabase host unreachable or offline ({e}). Operating locally with 100% direct speed!")

        # Initialize S3 client (secondary fallback)
        self.s3_client = None
        if settings.USE_S3 and not self.supabase:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION,
                )
            except Exception as e:
                print(f"[Storage] Warning: AWS S3 init failed: {e}. Falling back to local storage.")

    def _sanitize_path(self, filename: str) -> str:
        """Prevents directory traversal by keeping only the basename."""
        return os.path.basename(filename)

    def save_file(self, file_content: bytes, folder: str, filename: str) -> str:
        """
        Saves bytes to storage and returns a public-accessible URL.
        Falls through: Supabase → S3 → local path.
        """
        sanitized = self._sanitize_path(filename)

        # Always write locally first (cache + fallback)
        target_folder = self.base_dir / folder
        os.makedirs(target_folder, exist_ok=True)
        local_path = target_folder / sanitized
        with open(local_path, "wb") as f:
            f.write(file_content)

        # 1. Supabase Storage
        if self.supabase:
            storage_path = f"{folder}/{sanitized}"
            try:
                # upsert=True overwrites if already exists
                self.supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
                    path=storage_path,
                    file=file_content,
                    file_options={"upsert": "true"},
                )
                public_url = self.supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(storage_path)
                return public_url
            except Exception as e:
                print(f"[Storage] Supabase upload failed for {storage_path}: {e}. Trying next backend.")

        # 2. AWS S3
        if self.s3_client:
            s3_key = f"{folder}/{sanitized}"
            try:
                self.s3_client.upload_file(
                    str(local_path),
                    settings.AWS_BUCKET_NAME,
                    s3_key,
                    ExtraArgs={"ACL": "public-read"},
                )
                return f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
            except NoCredentialsError:
                print("[Storage] AWS credentials not found; falling back to local.")
            except Exception as e:
                print(f"[Storage] S3 upload failed: {e}. Falling back to local.")

        # 3. Local static path
        return f"/outputs/{folder}/{sanitized}"

    def get_local_path(self, folder: str, filename: str) -> Path:
        """Returns the absolute local path for a stored file."""
        sanitized = self._sanitize_path(filename)
        return self.base_dir / folder / sanitized

    def read_file(self, folder: str, filename: str) -> bytes:
        """Reads a file from local storage."""
        local_path = self.get_local_path(folder, filename)
        if not local_path.exists():
            raise FileNotFoundError(f"File not found in storage: {folder}/{filename}")
        with open(local_path, "rb") as f:
            return f.read()


storage_service = StorageService()
