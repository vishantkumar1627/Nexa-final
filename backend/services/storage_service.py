import os
import shutil
import boto3
from pathlib import Path
from typing import Tuple
from botocore.exceptions import NoCredentialsError
from shared.config import settings

class StorageService:
    def __init__(self):
        self.base_dir = Path(settings.STORAGE_DIR)
        # Ensure all folders exist
        self.floorplan_dir = self.base_dir / "floorplans"
        self.model3d_dir = self.base_dir / "models3d"
        self.render_dir = self.base_dir / "renders"
        
        # Ensure base directories exist
        os.makedirs(self.floorplan_dir, exist_ok=True)
        os.makedirs(self.model3d_dir, exist_ok=True)
        os.makedirs(self.render_dir, exist_ok=True)

        # Initialize S3 Client if enabled
        self.s3_client = None
        if settings.USE_S3:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_REGION
                )
            except Exception as e:
                print(f"Warning: Failed to initialize AWS S3 client: {e}. Falling back to local storage.")

    def _sanitize_path(self, filename: str) -> str:
        """Sanitizes file name to prevent local file inclusion/directory traversal attacks."""
        return os.path.basename(filename)

    def save_file(self, file_content: bytes, folder: str, filename: str) -> str:
        """Saves a binary file to either local storage or AWS S3 based on configs."""
        sanitized_filename = self._sanitize_path(filename)
        
        # Define local target path
        target_folder = self.base_dir / folder
        os.makedirs(target_folder, exist_ok=True)
        local_path = target_folder / sanitized_filename

        # Write to local file
        with open(local_path, "wb") as f:
            f.write(file_content)

        # If AWS S3 is enabled and client successfully connected
        if settings.USE_S3 and self.s3_client:
            s3_key = f"{folder}/{sanitized_filename}"
            try:
                self.s3_client.upload_file(
                    str(local_path),
                    settings.AWS_BUCKET_NAME,
                    s3_key,
                    ExtraArgs={'ACL': 'public-read'}
                )
                # Return standard S3 public URL
                return f"https://{settings.AWS_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"
            except NoCredentialsError:
                print("AWS credentials not found. S3 upload failed; falling back to local file path reference.")
            except Exception as e:
                print(f"S3 Upload failed: {e}. Falling back to local file path reference.")

        # Return local static mount URL path
        return f"/outputs/{folder}/{sanitized_filename}"

    def get_local_path(self, folder: str, filename: str) -> Path:
        """Helper to fetch exact safe absolute local path of a file."""
        sanitized_filename = self._sanitize_path(filename)
        return self.base_dir / folder / sanitized_filename

    def read_file(self, folder: str, filename: str) -> bytes:
        """Retrieve binary file contents from storage."""
        local_path = self.get_local_path(folder, filename)
        if not local_path.exists():
            raise FileNotFoundError(f"File not found in storage: {folder}/{filename}")
        
        with open(local_path, "rb") as f:
            return f.read()

storage_service = StorageService()
