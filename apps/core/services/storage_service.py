"""
Google Cloud Storage service for handling file uploads.
"""
import logging
import uuid
import os
from datetime import timedelta
from typing import Dict, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class GCSStorageService:
    """
    Service for generating signed URLs for direct GCS uploads.
    
    Uses signed URLs to allow frontend to upload directly to GCS,
    avoiding backend file handling for better performance.
    """
    
    def __init__(self):
        self.bucket_name = getattr(settings, 'GCS_BUCKET_NAME', '')
        self.project_id = getattr(settings, 'GCS_PROJECT_ID', '')
        self._client = None
        self._bucket = None
    
    @property
    def client(self):
        """Lazy-load GCS client."""
        if not self._client:
            from google.cloud import storage
            
            credentials_path = getattr(settings, 'GCS_CREDENTIALS_PATH', '')
            if credentials_path and os.path.exists(credentials_path):
                self._client = storage.Client.from_service_account_json(credentials_path)
            else:
                # Use application default credentials
                self._client = storage.Client(project=self.project_id)
        
        return self._client
    
    @property
    def bucket(self):
        """Lazy-load GCS bucket."""
        if not self._bucket:
            self._bucket = self.client.bucket(self.bucket_name)
        return self._bucket
    
    def upload_image(
        self,
        file,
        folder: str = 'shops/covers',
        max_size_mb: int = 5
    ) -> Optional[str]:
        """
        Upload an image file directly to GCS.
        
        Args:
            file: File object from request.FILES
            folder: Folder path within bucket (e.g., 'shops/covers')
            max_size_mb: Maximum file size in MB
            
        Returns:
            Public URL of uploaded file, or None if failed
        """
        try:
            # Validate file size
            if file.size > max_size_mb * 1024 * 1024:
                logger.error(f"File too large: {file.size} bytes (max {max_size_mb}MB)")
                return None
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp']
            if file.content_type not in allowed_types:
                logger.error(f"Invalid file type: {file.content_type}")
                return None
            
            # Generate unique filename
            ext = os.path.splitext(file.name)[1]
            filename = f"{uuid.uuid4()}{ext}"
            blob_name = f"{folder}/{filename}"
            
            # Upload to GCS
            blob = self.bucket.blob(blob_name)
            blob.upload_from_file(file, content_type=file.content_type)
            
            # Make blob publicly readable
            blob.make_public()
            
            # Return public URL
            public_url = blob.public_url
            logger.info(f"Uploaded image to {blob_name}")
            
            return public_url
            
        except Exception as e:
            logger.error(f"Failed to upload image: {str(e)}")
            return None
    
    def delete_image(self, image_url: str) -> bool:
        """
        Delete an image from GCS given its URL.
        
        Args:
            image_url: Public URL of the image
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Extract blob name from URL
            if self.bucket_name not in image_url:
                logger.warning(f"URL does not match bucket: {image_url}")
                return False
            
            blob_name = image_url.split(f'{self.bucket_name}/')[1]
            blob = self.bucket.blob(blob_name)
            blob.delete()
            
            logger.info(f"Deleted image: {blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete image: {str(e)}")
            return False
    
    def make_public(self, blob_name: str) -> bool:
        """
        Make a blob publicly accessible.
        
        Args:
            blob_name: Name of the blob in the bucket
            
        Returns:
            True if successful, False otherwise
        """
        try:
            blob = self.bucket.blob(blob_name)
            blob.make_public()
            logger.info(f"Made blob public: {blob_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to make blob public: {str(e)}")
            return False
    
    @staticmethod
    def _get_extension_from_content_type(content_type: str) -> str:
        """Get file extension from content type."""
        extensions = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif'
        }
        return extensions.get(content_type.lower(), '.jpg')


# Singleton instance
gcs_storage = GCSStorageService()
