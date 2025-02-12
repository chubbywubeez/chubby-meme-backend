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
            # Test connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise

    def add_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """Add a new job to the queue with detailed status tracking"""
        try:
            # Add timestamp and initial status
            job_data.update({
                'created_at': datetime.utcnow().isoformat(),
                'status': JOB_STATUS["QUEUED"],
                'status_history': [{
                    'status': JOB_STATUS["QUEUED"],
                    'timestamp': datetime.utcnow().isoformat(),
                    'message': 'Job added to queue'
                }]
            })
            
            # Store job data with TTL
            success = self.redis_client.setex(
                f"job:{job_id}",
                QUEUE_CONFIG['job_ttl'],
                json.dumps(job_data)
            )
            
            if success:
                # Add to active jobs set
                self.redis_client.sadd("active_jobs", job_id)
                logger.info(f"Successfully added job {job_id} to queue")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error adding job to Redis: {str(e)}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed job status including history"""
        try:
            job_data = self.redis_client.get(f"job:{job_id}")
            if not job_data:
                logger.info(f"No data found for job {job_id}")
                return None
                
            data = json.loads(job_data)
            logger.info(f"Retrieved status for job {job_id}: {data.get('status', 'unknown')}")
            return data
            
        except Exception as e:
            logger.error(f"Error getting job status from Redis: {str(e)}")
            return None

    def update_job_status(self, job_id: str, status: str, additional_data: Dict[str, Any] = None) -> bool:
        """Update job status with history tracking"""
        try:
            job_data = self.get_job_status(job_id)
            if not job_data:
                logger.warning(f"Cannot update status for non-existent job {job_id}")
                return False

            # Update status and timestamp
            current_time = datetime.utcnow().isoformat()
            job_data['status'] = status
            job_data['updated_at'] = current_time
            
            # Add to status history
            if 'status_history' not in job_data:
                job_data['status_history'] = []
                
            history_entry = {
                'status': status,
                'timestamp': current_time
            }
            
            # Add error information to history if present
            if additional_data and 'error' in additional_data:
                history_entry['error'] = additional_data['error']
                
            job_data['status_history'].append(history_entry)
            
            # Update additional data
            if additional_data:
                job_data.update(additional_data)
            
            # Store updated job data with remaining TTL
            ttl = self.redis_client.ttl(f"job:{job_id}")
            if ttl < 0:
                ttl = QUEUE_CONFIG['job_ttl']
                
            success = self.redis_client.setex(
                f"job:{job_id}",
                ttl,
                json.dumps(job_data)
            )
            
            # Remove from active jobs if completed or failed
            if status in [JOB_STATUS["COMPLETED"], JOB_STATUS["FAILED"]]:
                self.redis_client.srem("active_jobs", job_id)
            
            if success:
                logger.info(f"Successfully updated job {job_id} status to {status}")
            return success
            
        except Exception as e:
            logger.error(f"Error updating job status in Redis: {str(e)}")
            return False

    def cleanup_stale_jobs(self, max_age_seconds: int = 1800) -> int:
        """Clean up stale jobs with detailed logging"""
        try:
            cleaned_count = 0
            cutoff_time = datetime.utcnow() - timedelta(seconds=max_age_seconds)
            
            # Get all active jobs
            active_jobs = self.redis_client.smembers("active_jobs")
            logger.info(f"Found {len(active_jobs)} active jobs to check")
            
            for job_id in active_jobs:
                job_id = job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id
                job_data = self.get_job_status(job_id)
                
                if not job_data:
                    logger.warning(f"Removing missing job {job_id} from active jobs")
                    self.redis_client.srem("active_jobs", job_id)
                    cleaned_count += 1
                    continue
                
                try:
                    created_at = datetime.fromisoformat(job_data.get('created_at', '2000-01-01T00:00:00'))
                except (ValueError, TypeError):
                    logger.error(f"Invalid created_at timestamp for job {job_id}")
                    created_at = datetime.min
                
                if created_at < cutoff_time:
                    logger.info(f"Cleaning up stale job {job_id} created at {created_at}")
                    self.update_job_status(
                        job_id,
                        JOB_STATUS["FAILED"],
                        {
                            "error": "Job timed out",
                            "cleanup_time": datetime.utcnow().isoformat()
                        }
                    )
                    cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} stale jobs")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up stale jobs: {str(e)}")
            return 0

    def get_queue_length(self) -> int:
        """Get current queue length with error handling"""
        try:
            length = self.redis_client.scard("active_jobs")
            logger.info(f"Current queue length: {length}")
            return length
        except Exception as e:
            logger.error(f"Error getting queue length from Redis: {str(e)}")
            return 0

    def store_meme_data(self, meme_id: str, meme_data: Dict[str, Any], ttl: int = None) -> bool:
        """Store meme data with TTL and validation"""
        try:
            if ttl is None:
                ttl = QUEUE_CONFIG["result_ttl"]
            
            # Add metadata
            meme_data.update({
                'created_at': datetime.utcnow().isoformat(),
                'ttl': ttl
            })
            
            # Validate required fields
            required_fields = ['imageUrl', 'type', 'memeId']
            missing_fields = [field for field in required_fields if field not in meme_data]
            if missing_fields:
                logger.error(f"Missing required fields for meme {meme_id}: {missing_fields}")
                return False
            
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
        """Retrieve meme data from Redis with detailed logging"""
        try:
            meme_data = self.redis_client.get(f"meme:{meme_id}")
            if not meme_data:
                logger.info(f"No meme data found for {meme_id}")
                return None
                
            data = json.loads(meme_data)
            logger.info(f"Retrieved meme data for {meme_id}: {json.dumps(data, indent=2)}")
            
            # Validate required fields in retrieved data
            required_fields = ['imageUrl', 'type', 'memeId']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                logger.error(f"Retrieved meme data missing required fields: {missing_fields}")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"Error getting meme data from Redis: {str(e)}")
            return None

# Create a singleton instance
redis_service = RedisService() 