"""
Media proxy views for serving private GCS content.
"""
from django.http import HttpResponse, Http404
from django.views import View
from apps.core.services.storage_service import gcs_storage
import logging

logger = logging.getLogger(__name__)


class ShopCoverImageProxyView(View):
    """
    Proxy view for serving shop cover images from GCS.
    
    This allows serving images from private GCS buckets through the backend,
    working around organization policies that prevent public bucket access.
    """
    
    def get(self, request, filename):
        """
        Serve image from GCS bucket.
        
        Args:
            filename: Image filename (e.g., 'abc123.jpg')
        """
        try:
            blob_name = f"shops/covers/{filename}"
            
            # Get blob from GCS
            blob = gcs_storage.bucket.blob(blob_name)
            
            # Check if blob exists
            if not blob.exists():
                logger.warning(f"Image not found: {blob_name}")
                raise Http404("Image not found")
            
            # Download blob content
            image_data = blob.download_as_bytes()
            
            # Determine content type
            content_type = blob.content_type or 'image/jpeg'
            
            # Return image response
            response = HttpResponse(image_data, content_type=content_type)
            response['Cache-Control'] = 'public, max-age=31536000'  # Cache for 1 year
            
            return response
            
        except Http404:
            raise
        except Exception as e:
            logger.error(f"Error serving image {filename}: {str(e)}")
            raise Http404("Image not found")
