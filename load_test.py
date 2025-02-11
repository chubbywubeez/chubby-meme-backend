import asyncio
import aiohttp
import time
import random
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000/api"
CONCURRENT_USERS = 5
TEST_DURATION = 300  # 5 minutes
TIMEOUT = aiohttp.ClientTimeout(total=None, connect=60, sock_read=60)  # More generous timeouts

# Sample prompts for testing
PERSONA_PROMPTS = [
    "a sarcastic cat",
    "a dad joke enthusiast",
    "a philosophical squirrel",
    "a tired programmer",
    "a fitness fanatic"
]

THEME_PROMPTS = [
    "Monday mornings",
    "pizza toppings",
    "social media",
    "gym life",
    "coding bugs"
]

async def simulate_user(session, user_id):
    """Simulate a single user's behavior"""
    try:
        # Generate meme request
        data = {
            "type": "single",
            "personaPrompt": random.choice(PERSONA_PROMPTS),
            "themePrompt": random.choice(THEME_PROMPTS),
            "charLimit": 75,
            "allowEmojis": True
        }

        print(f"User {user_id}: Starting meme generation with prompts: {data['personaPrompt']} / {data['themePrompt']}")
        start_time = time.time()

        # Submit meme generation request
        try:
            async with session.post(f"{BASE_URL}/generate-meme", json=data) as response:
                if response.status != 200:
                    response_text = await response.text()
                    print(f"User {user_id}: Failed to start job - Status: {response.status}, Response: {response_text}")
                    return
                
                job_data = await response.json()
                job_id = job_data.get("job_id")
                
                if not job_id:
                    print(f"User {user_id}: No job ID received - Response data: {job_data}")
                    return

                print(f"User {user_id}: Got job ID {job_id}")
        except Exception as e:
            print(f"User {user_id}: Error submitting job - {str(e)}")
            return

        # Poll for completion with exponential backoff
        backoff = 2
        max_backoff = 30
        poll_count = 0
        
        while True:
            if time.time() - start_time > 600:  # 10-minute timeout
                print(f"User {user_id}: Timeout waiting for meme")
                return

            try:
                async with session.get(f"{BASE_URL}/meme-status/{job_id}") as status_response:
                    if status_response.status != 200:
                        status_text = await status_response.text()
                        print(f"User {user_id}: Failed to check status - {status_response.status}, Response: {status_text}")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 1.5, max_backoff)
                        continue

                    status_data = await status_response.json()
                    status = status_data.get("status")
                    
                    poll_count += 1
                    if poll_count % 5 == 0:  # Log every 5th status check
                        print(f"User {user_id}: Status update - {status_data}")

                    if status == "completed":
                        end_time = time.time()
                        duration = end_time - start_time
                        print(f"User {user_id}: Meme completed in {duration:.2f} seconds")
                        return
                    elif status == "failed":
                        error = status_data.get("error", "No error details provided")
                        print(f"User {user_id}: Meme generation failed - Error: {error}")
                        return

            except Exception as e:
                print(f"User {user_id}: Error checking status - {str(e)}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, max_backoff)
                continue

            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, max_backoff)

    except Exception as e:
        print(f"User {user_id}: Error - {str(e)}")
        import traceback
        print(f"User {user_id}: Traceback - {traceback.format_exc()}")

async def main():
    """Main load test function"""
    print(f"Starting load test with {CONCURRENT_USERS} concurrent users")
    start_time = datetime.now()

    # Create shared session for all users with custom timeout
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        # First, check if the server is healthy
        try:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status != 200:
                    print("Server is not healthy, aborting test")
                    return
                health_data = await response.json()
                print(f"Server health check: {health_data}")
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return

        # Create tasks for all users
        tasks = []
        for i in range(CONCURRENT_USERS):
            # Add some randomization to start times
            await asyncio.sleep(random.uniform(0, 2))
            task = asyncio.create_task(simulate_user(session, i))
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"\nLoad test completed in {duration:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main()) 