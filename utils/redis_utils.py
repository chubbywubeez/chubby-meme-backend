import os
import redis
import json
from datetime import datetime
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
        if REDIS_URL.startswith('rediss://'):
            # For TLS connections on Heroku
            self.redis_client = redis.from_url(
                REDIS_URL,
                ssl_cert_reqs=None,
                decode_responses=True
            )
        else:
            # For non-TLS connections (local development)
            self.redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True
            )
        self._ensure_connection()

    def _ensure_connection(self):
        """Verify Redis connection is working"""
        try:
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise Exception(f"Failed to connect to Redis: {str(e)}")

    def add_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """Add a new job to the queue"""
        try:
            job_info = {
                "status": JOB_STATUS["QUEUED"],
                "data": job_data,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            success = self.redis_client.setex(
                f"job:{job_id}",
                QUEUE_CONFIG["job_ttl"],
                json.dumps(job_info)
            )
            if success:
                logger.info(f"Successfully added job {job_id} to queue")
            return success
        except Exception as e:
            logger.error(f"Error adding job to queue: {str(e)}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a job"""
        try:
            job_data = self.redis_client.get(f"job:{job_id}")
            if job_data:
                logger.info(f"Retrieved status for job {job_id}")
                return json.loads(job_data)
            logger.info(f"No data found for job {job_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            return None

    def update_job_status(self, job_id: str, status: str, additional_data: Dict[str, Any] = None) -> bool:
        """Update the status of a job"""
        try:
            job_data = self.get_job_status(job_id)
            if not job_data:
                logger.warning(f"Cannot update status for non-existent job {job_id}")
                return False

            job_data["status"] = status
            job_data["updated_at"] = datetime.utcnow().isoformat()
            
            if additional_data:
                job_data.update(additional_data)

            success = self.redis_client.setex(
                f"job:{job_id}",
                QUEUE_CONFIG["job_ttl"],
                json.dumps(job_data)
            )
            if success:
                logger.info(f"Successfully updated job {job_id} status to {status}")
            return success
        except Exception as e:
            logger.error(f"Error updating job status: {str(e)}")
            return False

    def store_meme_data(self, meme_id: str, meme_data: Dict[str, Any], ttl: int = None) -> bool:
        """Store meme data in Redis"""
        try:
            if ttl is None:
                ttl = QUEUE_CONFIG["result_ttl"]
                
            success = self.redis_client.setex(
                f"meme:{meme_id}",
                ttl,
                json.dumps(meme_data)
            )
            if success:
                logger.info(f"Successfully stored meme data for {meme_id}")
            return success
        except Exception as e:
            logger.error(f"Error storing meme data: {str(e)}")
            return False

    def get_meme_data(self, meme_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve meme data from Redis"""
        try:
            meme_data = self.redis_client.get(f"meme:{meme_id}")
            if meme_data:
                logger.info(f"Retrieved meme data for {meme_id}")
                return json.loads(meme_data)
            logger.info(f"No meme data found for {meme_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting meme data: {str(e)}")
            return None

    def get_queue_length(self) -> int:
        """Get the current number of jobs in the queue"""
        try:
            keys = self.redis_client.keys("job:*")
            return len(keys)
        except Exception as e:
            logger.error(f"Error getting queue length: {str(e)}")
            return 0

# Create a singleton instance
redis_service = RedisService() 