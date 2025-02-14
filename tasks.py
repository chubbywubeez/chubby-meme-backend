from celery_config import celery_app
from scripts.meme_generator import simulate_tweet
from utils.redis_utils import redis_service, JOB_STATUS
import time
from io import BytesIO
import cloudinary
import cloudinary.uploader
import logging
import traceback

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    name='tasks.generate_meme',
    max_retries=3,
    soft_time_limit=240,
    time_limit=300
)
def generate_meme(self, job_id, request_data):
    """
    Celery task for meme generation
    """
    try:
        start_time = time.time()
        logger.info(f"Starting meme generation task for job {job_id}")
        
        # Update job status
        redis_service.update_job_status(job_id, JOB_STATUS["PROCESSING"])
        
        # Generate meme
        try:
            generation_start_time = time.time()
            image = simulate_tweet(
                persona_prompt=request_data['personaPrompt'],
                theme_prompt=request_data['themePrompt'],
                char_limit=request_data.get('charLimit', 75),
                allow_emojis=request_data.get('allowEmojis', False)
            )
            generation_duration = time.time() - generation_start_time
            
            if not image:
                raise ValueError("Meme generation returned None")
                
        except Exception as e:
            logger.error(f"Meme generation failed: {str(e)}")
            redis_service.update_job_status(
                job_id,
                JOB_STATUS["FAILED"],
                {"error": str(e), "stage": "generation"}
            )
            raise
            
        # Upload to Cloudinary
        try:
            upload_start_time = time.time()
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            
            result = cloudinary.uploader.upload(
                buffered.getvalue(),
                folder="memes",
                resource_type="image",
                context={
                    'alt': 'Chubby Wubeez Generated Meme',
                    'caption': 'Generated with AI-powered humor'
                }
            )
            upload_duration = time.time() - upload_start_time
            
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            redis_service.update_job_status(
                job_id,
                JOB_STATUS["FAILED"],
                {"error": str(e), "stage": "upload"}
            )
            raise
            
        # Store results
        total_duration = time.time() - start_time
        meme_data = {
            "imageUrl": result['secure_url'],
            "publicUrl": result['secure_url'],
            "type": request_data.get('type', 'single'),
            "memeId": job_id,
            "timing": {
                "total_duration": round(total_duration, 2),
                "generation_duration": round(generation_duration, 2),
                "upload_duration": round(upload_duration, 2)
            }
        }
        
        redis_service.store_meme_data(job_id, meme_data)
        redis_service.update_job_status(
            job_id,
            JOB_STATUS["COMPLETED"],
            {"result": meme_data}
        )
        
        logger.info(f"Meme generation completed for job {job_id}")
        return meme_data
        
    except Exception as e:
        logger.error(f"Task failed: {str(e)}\n{traceback.format_exc()}")
        # Retry the task if appropriate
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)
        raise 