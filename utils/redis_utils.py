import os
import redis
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Job status constants
JOB_STATUS = {
    'QUEUED': 'queued',
    'PROCESSING': 'processing',
    'COMPLETED': 'completed',
    'FAILED': 'failed'
}

# Queue configuration
QUEUE_CONFIG = {
    'default_timeout': 300,  # 5 minutes
    'max_retries': 3,
    'retry_delay': 60,  # 1 minute
    'job_ttl': 24 * 60 * 60,  # 24 hours
    'result_ttl': 24 * 60 * 60  # 24 hours
}

class RedisService:
    def __init__(self):
        self.redis_url = REDIS_URL
        try:
            self.redis_client = redis.from_url(self.redis_url)
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    def add_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """Add a new job to the queue"""
        try:
            job_data['created_at'] = datetime.utcnow().isoformat()
            job_data['status'] = JOB_STATUS["QUEUED"]
            self.redis_client.set(f"job:{job_id}", json.dumps(job_data))
            self.redis_client.sadd("active_jobs", job_id)
            logger.info(f"Successfully added job {job_id} to queue")
            return True
        except Exception as e:
            logger.error(f"Error adding job to Redis: {str(e)}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a job"""
        try:
            job_data = self.redis_client.get(f"job:{job_id}")
            if not job_data:
                logger.info(f"No data found for job {job_id}")
                return None
            logger.info(f"Retrieved status for job {job_id}")
            return json.loads(job_data)
        except Exception as e:
            logger.error(f"Error getting job status from Redis: {str(e)}")
            return None

    def update_job_status(self, job_id: str, status: str, additional_data: Dict[str, Any] = None) -> bool:
        """Update the status of a job"""
        try:
            job_data = self.get_job_status(job_id)
            if not job_data:
                logger.warning(f"Cannot update status for non-existent job {job_id}")
                return False

            job_data['status'] = status
            if additional_data:
                job_data.update(additional_data)
            
            job_data['updated_at'] = datetime.utcnow().isoformat()
            self.redis_client.set(f"job:{job_id}", json.dumps(job_data))
            
            # Remove from active jobs if completed or failed
            if status in [JOB_STATUS["COMPLETED"], JOB_STATUS["FAILED"]]:
                self.redis_client.srem("active_jobs", job_id)
            
            logger.info(f"Successfully updated job {job_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating job status in Redis: {str(e)}")
            return False

    def store_meme_data(self, meme_id: str, meme_data: Dict[str, Any], ttl: int = None) -> bool:
        """Store meme data in Redis"""
        try:
            if ttl is None:
                ttl = QUEUE_CONFIG["result_ttl"]
                
            meme_data['created_at'] = datetime.utcnow().isoformat()
            success = self.redis_client.setex(
                f"meme:{meme_id}",
                ttl,
                json.dumps(meme_data)
            )
            if success:
                logger.info(f"Successfully stored meme data for {meme_id}")
            return success
        except Exception as e:
            logger.error(f"Error storing meme data in Redis: {str(e)}")
            return False

    def get_meme_data(self, meme_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve meme data from Redis"""
        try:
            meme_data = self.redis_client.get(f"meme:{meme_id}")
            if not meme_data:
                logger.info(f"No meme data found for {meme_id}")
                return None
            logger.info(f"Retrieved meme data for {meme_id}")
            return json.loads(meme_data)
        except Exception as e:
            logger.error(f"Error getting meme data from Redis: {str(e)}")
            return None

    def get_queue_length(self) -> int:
        """Get the current number of jobs in the queue"""
        try:
            return self.redis_client.scard("active_jobs")
        except Exception as e:
            logger.error(f"Error getting queue length from Redis: {str(e)}")
            return 0

    def cleanup_stale_jobs(self, max_age_seconds: int = 1800) -> int:
        """
        Clean up jobs older than max_age_seconds
        Returns the number of jobs cleaned up
        """
        try:
            cleaned_count = 0
            cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)
            
            # Get all active jobs
            active_jobs = self.redis_client.smembers("active_jobs")
            
            for job_id in active_jobs:
                job_id = job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id
                job_data = self.get_job_status(job_id)
                
                if not job_data:
                    # Job data missing, remove from active jobs
                    self.redis_client.srem("active_jobs", job_id)
                    cleaned_count += 1
                    continue
                
                created_at = datetime.fromisoformat(job_data.get('created_at', '2000-01-01T00:00:00'))
                
                if created_at < cutoff_time:
                    # Job is too old, mark as failed and remove from active jobs
                    self.update_job_status(
                        job_id,
                        JOB_STATUS["FAILED"],
                        {"error": "Job timed out"}
                    )
                    cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} stale jobs")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up stale jobs: {str(e)}")
            return 0

# Create a singleton instance
redis_service = RedisService() 