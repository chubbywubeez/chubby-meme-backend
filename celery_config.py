from celery import Celery
from os import getenv
import os

# Load environment variables if needed
redis_url = getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'chubby_meme_generator',
    broker=redis_url,
    backend=redis_url,
    broker_connection_retry_on_startup=True
)

# Configure Celery
celery_app.conf.update(
    worker_prefetch_multiplier=1,  # Each worker handles one task at a time
    task_acks_late=True,  # Tasks are acknowledged after completion
    task_time_limit=300,  # 5-minute timeout for tasks
    task_soft_time_limit=240,  # Soft timeout at 4 minutes
    worker_concurrency=os.cpu_count(),  # Number of worker processes
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Optional: Configure task routing
celery_app.conf.task_routes = {
    'tasks.generate_meme': {'queue': 'meme_generation'},
} 