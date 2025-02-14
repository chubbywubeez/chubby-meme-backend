web: uvicorn app:app --host 0.0.0.0 --port $PORT
worker: celery -A tasks worker -l INFO -Q meme_generation -c 4
