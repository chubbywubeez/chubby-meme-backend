from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
from pydantic import BaseModel
import os
from io import BytesIO
import base64
from scripts.meme_generator import simulate_tweet
import cloudinary
import cloudinary.uploader
from os import getenv
import asyncio
import json
import uuid
from datetime import datetime
from utils.redis_utils import redis_service, JOB_STATUS
from utils.logger import get_logger
import random

logger = get_logger(__name__)

app = FastAPI(
    title="Chubby Meme API",
    description="API for generating memes",
    version="1.0.0",
    root_path=""  # Add this to ensure no prefix
)

# Define allowed origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://funny-flan-ea111b.netlify.app",
    "https://chubby-meme-backend-production.up.railway.app",
    "https://cards-dev.twitter.com",  # For Twitter card validation
    "https://twitter.com",
    "https://x.com"
]

# Define timeouts
REQUEST_TIMEOUT = 25  # Heroku's timeout is 30s, so we set this lower

# Enhanced CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://funny-flan-ea111b.netlify.app",
        "http://localhost:3000",
        "https://chubby-meme-backend-production.up.railway.app"  # Add this
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Update the Cloudinary configuration
cloudinary.config( 
    cloud_name = getenv('CLOUDINARY_CLOUD_NAME'),
    api_key = getenv('CLOUDINARY_API_KEY'),
    api_secret = getenv('CLOUDINARY_API_SECRET')
)

class MemeRequest(BaseModel):
    type: str = "single"
    personaPrompt: str
    themePrompt: str
    charLimit: int = 75
    allowEmojis: bool = False

# Common CORS headers function
def get_cors_headers(request: Request):
    origin = request.headers.get('origin', '')
    if os.getenv('ENVIRONMENT') == 'development' or origin in ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin or "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600"
        }
    return {
        "Access-Control-Allow-Origin": origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[0],
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
        "Access-Control-Max-Age": "3600"
    }

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    try:
        response = await call_next(request)
        for key, value in get_cors_headers(request).items():
            response.headers[key] = value
        return response
    except Exception as e:
        error_msg = str(e)
        status_code = 503 if "overloaded" in error_msg.lower() or "timeout" in error_msg.lower() else 500
        return JSONResponse(
            content={"detail": error_msg},
            status_code=status_code,
            headers=get_cors_headers(request)
        )

@app.options("/generate-meme")
async def generate_meme_preflight(request: Request):
    origin = request.headers.get('origin', '')
    if origin in ALLOWED_ORIGINS:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
            "Access-Control-Max-Age": "3600",
        }
        return JSONResponse(content={"message": "Accepted"}, headers=headers)
    return JSONResponse(content={"message": "Invalid origin"}, status_code=400)

@app.post("/generate-meme")
async def generate_meme(request: MemeRequest, req: Request, background_tasks: BackgroundTasks):
    try:
        # Check queue length to prevent overload
        queue_length = redis_service.get_queue_length()
        logger.info(f"Current queue length: {queue_length}")

        if queue_length > 100:  # Adjust this number based on your capacity
            logger.warning("Queue is full, rejecting new requests")
            return JSONResponse(
                content={"detail": "Server is currently busy. Please try again later."},
                status_code=503,
                headers=get_cors_headers(req)
            )

        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        logger.info(f"Generated new job ID: {job_id}")
        
        # Store the job in Redis with initial status
        job_data = {
            "request": request.dict(),
            "created_at": datetime.utcnow().isoformat()
        }
        
        if not redis_service.add_job(job_id, job_data):
            logger.error("Failed to create job in Redis")
            raise HTTPException(status_code=500, detail="Failed to create job")
        
        logger.info(f"Successfully stored job {job_id} in Redis")
        
        # Add the job to background tasks
        background_tasks.add_task(process_meme_generation, job_id, request)
        
        logger.info(f"Job {job_id} created successfully")
        return JSONResponse(
            content={"job_id": job_id, "status": JOB_STATUS["QUEUED"]},
            headers=get_cors_headers(req)
        )
        
    except Exception as e:
        logger.error(f"Error initiating job: {str(e)}")
        return JSONResponse(
            content={"detail": "Failed to start job"},
            status_code=500,
            headers=get_cors_headers(req)
        )

@app.get("/meme-status/{job_id}")
async def get_meme_status(job_id: str, request: Request):
    try:
        logger.info(f"Checking status for job {job_id}")
        job_data = redis_service.get_job_status(job_id)
        
        if not job_data:
            logger.warning(f"Job {job_id} not found")
            return JSONResponse(
                content={"detail": "Job not found"},
                status_code=404,
                headers=get_cors_headers(request)
            )
            
        logger.info(f"Job {job_id} status: {job_data.get('status')}")
        return JSONResponse(
            content=job_data,
            headers=get_cors_headers(request)
        )
        
    except Exception as e:
        logger.error(f"Error getting status for job {job_id}: {str(e)}")
        return JSONResponse(
            content={"detail": str(e)},
            status_code=500,
            headers=get_cors_headers(request)
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "redis": redis_service.check_health()}

@app.get("/meme/{meme_id}")
async def get_meme(meme_id: str, request: Request):
    try:
        meme_data = redis_service.get_meme_data(meme_id)
        
        if not meme_data:
            logger.warning(f"Meme {meme_id} not found")
            return JSONResponse(
                content={"detail": "Meme not found"},
                status_code=404,
                headers=get_cors_headers(request)
            )
            
        logger.info(f"Retrieved meme {meme_id}")
        return JSONResponse(
            content=meme_data,
            headers=get_cors_headers(request)
        )
        
    except Exception as e:
        logger.error(f"Error getting meme {meme_id}: {str(e)}")
        return JSONResponse(
            content={"detail": str(e)},
            status_code=500,
            headers=get_cors_headers(request)
        )

@app.get("/m/{meme_id}", response_class=HTMLResponse)
async def share_meme(meme_id: str, request: Request):
    try:
        logger.info(f"""
        ====== Share Request Received ======
        Meme ID: {meme_id}
        Request URL: {request.url}
        Headers: {request.headers}
        ============================
        """)
        
        meme_data = redis_service.get_meme_data(meme_id)
        logger.info(f"Meme data retrieved: {meme_data}")
        
        if not meme_data:
            raise HTTPException(status_code=404, detail="Meme not found")
            
        # Get the image URL and optimize it for Twitter
        image_url = meme_data.get('imageUrl')
        if 'res.cloudinary.com' in image_url:
            # Add Cloudinary transformations for optimal Twitter card
            url_parts = image_url.split('/upload/')
            if len(url_parts) == 2:
                # Twitter large card optimal dimensions (2:1 ratio)
                # w_1200,h_600 is Twitter's recommended size
                image_url = f"{url_parts[0]}/upload/w_1200,h_600,c_pad,b_black/{url_parts[1]}"
        
        # Get the base URL for the API
        base_url = str(request.base_url).rstrip('/')
        
        # Get absolute URL for the share endpoint
        share_url = f"{base_url}/m/{meme_id}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Make Money Making Memes with Chubby Wubeez!</title>
            
            <!-- Twitter Card data -->
            <meta name="twitter:card" content="summary_large_image">
            <meta name="twitter:site" content="@ChubbyWubeez">
            <meta name="twitter:title" content="Make Money Making Memes with Chubby Wubeez!">
            <meta name="twitter:description" content="AI-powered meme generator">
            <meta name="twitter:image" content="{image_url}">
            <meta name="twitter:image:alt" content="AI-generated meme">
            
            <!-- Open Graph data -->
            <meta property="og:title" content="Make Money Making Memes with Chubby Wubeez!">
            <meta property="og:type" content="website">
            <meta property="og:url" content="{share_url}">
            <meta property="og:image" content="{image_url}">
            <meta property="og:description" content="AI-powered meme generator">
            <meta property="og:site_name" content="Chubby Wubeez Meme Generator">
            
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    background: black;
                    color: white;
                    font-family: system-ui, -apple-system, sans-serif;
                    min-height: 100vh;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }}
                
                .container {{
                    width: 100%;
                    max-width: 1200px;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 20px;
                }}
                
                .image-container {{
                    width: 100%;
                    max-height: 90vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    overflow: hidden;
                    border-radius: 12px;
                }}
                
                img {{
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                    max-height: 90vh;
                }}
                
                h1 {{
                    text-align: center;
                    font-size: clamp(1.5rem, 4vw, 2.5rem);
                    margin: 20px 0;
                }}
                
                .button {{
                    display: inline-block;
                    background: #ff7b00;
                    color: white;
                    padding: 12px 24px;
                    border-radius: 24px;
                    text-decoration: none;
                    font-weight: bold;
                    font-size: clamp(1rem, 3vw, 1.25rem);
                    transition: background-color 0.2s;
                }}
                
                .button:hover {{
                    background: #ffa149;
                }}
                
                @media (max-width: 768px) {{
                    .container {{
                        padding: 10px;
                    }}
                    
                    img {{
                        border-radius: 8px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="image-container">
                    <img src="{image_url}" alt="AI-generated meme">
                </div>
                <h1>Make Money Making Memes with Chubby Wubeez!</h1>
                <a href="https://funny-flan-ea111b.netlify.app" class="button">
                    Create Your Own Meme
                </a>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Error serving share page for meme {meme_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
async def test_endpoint():
    return {"status": "ok", "message": "API is working"}

@app.get("/")
async def root():
    return HTMLResponse(content="""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <title>Chubby Wubeez Meme API</title>
            <style>
                body {
                    margin: 0;
                    padding: 20px;
                    font-family: system-ui, -apple-system, sans-serif;
                    background: black;
                    color: white;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    text-align: center;
                }
                h1 {
                    color: #ff7b00;
                }
                .status {
                    color: #4ade80;
                    margin: 20px 0;
                }
            </style>
        </head>
        <body>
            <div>
                <h1>Chubby Wubeez Meme API</h1>
                <p class="status">✅ API is running</p>
                <p>Visit <a href="https://funny-flan-ea111b.netlify.app" style="color: #ff7b00;">Chubby Wubeez</a> to create memes!</p>
            </div>
        </body>
        </html>
    """)

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

async def process_meme_generation(job_id: str, request: MemeRequest):
    try:
        logger.info(f"""
        ====== Starting Meme Generation ======
        Job ID: {job_id}
        Persona Prompt: {request.personaPrompt}
        Theme Prompt: {request.themePrompt}
        ===================================
        """)
        
        redis_service.update_job_status(job_id, JOB_STATUS["PROCESSING"])
        
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                # Generate meme
                logger.info("Generating meme image...")
                image = simulate_tweet(
                    persona_prompt=request.personaPrompt,
                    theme_prompt=request.themePrompt,
                    char_limit=request.charLimit,
                    allow_emojis=request.allowEmojis
                )
                
                logger.info("Uploading to Cloudinary...")
                # Process and store result
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                
                # Log Cloudinary upload attempt
                logger.info("Starting Cloudinary upload...")
                result = cloudinary.uploader.upload(
                    buffered.getvalue(),
                    folder="memes",
                    resource_type="image",
                    context={
                        'alt': 'Chubby Wubeez Generated Meme',
                        'caption': 'Generated with AI-powered humor',
                        'twitter_card': 'summary_large_image',
                        'twitter_site': '@ChubbyWubeez',
                        'twitter_creator': '@ChubbyWubeez',
                        'twitter_title': 'Check out this meme from Chubby Wubeez!',
                        'twitter_description': 'Generated with AI-powered humor'
                    }
                )
                
                logger.info(f"""
                ====== Cloudinary Upload Result ======
                Secure URL: {result['secure_url']}
                Resource Type: {result.get('resource_type')}
                Format: {result.get('format')}
                Size: {result.get('bytes')} bytes
                =====================================
                """)
                
                # Store meme data for sharing
                meme_data = {
                    "imageUrl": result['secure_url'],
                    "publicUrl": result['secure_url'],
                    "type": request.type,
                    "memeId": job_id
                }
                
                logger.info(f"""
                ====== Storing Meme Data ======
                Meme ID: {job_id}
                Image URL: {meme_data['imageUrl']}
                Public URL: {meme_data['publicUrl']}
                ============================
                """)
                
                redis_service.store_meme_data(job_id, meme_data)
                
                redis_service.update_job_status(
                    job_id,
                    JOB_STATUS["COMPLETED"],
                    {
                        "result": {
                            "imageUrl": result['secure_url'],
                            "type": request.type,
                            "memeId": job_id
                        }
                    }
                )
                logger.info(f"Job {job_id} completed successfully")
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout during meme generation for job {job_id}")
            redis_service.update_job_status(
                job_id,
                JOB_STATUS["FAILED"],
                {"error": "Generation timed out"}
            )
            return
            
    except Exception as e:
        logger.error(f"""
        ====== Error in Meme Generation ======
        Job ID: {job_id}
        Error: {str(e)}
        ===================================
        """)
        redis_service.update_job_status(
            job_id,
            JOB_STATUS["FAILED"],
            {"error": str(e)}
        )

@app.get("/routes")
async def list_routes():
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "methods": route.methods,
            "name": route.name
        })
    return {"routes": routes}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080) 