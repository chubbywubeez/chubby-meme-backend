import json
import time
import schedule
from datetime import datetime
import os
import sys
from openai import OpenAI
from dotenv import load_dotenv
import random
from difflib import SequenceMatcher

# Add the backend directory to Python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BACKEND_DIR)

# Now we can import from utils
from utils.logger import get_logger

# Configure logging
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Constants
PERSONA_ASSISTANT_ID = "asst_mdB3xM0OczHqAKOB3EBrcp72"
CACHE_FILE = os.path.join(BACKEND_DIR, "cache", "personas.json")
CACHE_DIR = os.path.join(BACKEND_DIR, "cache")

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

def wait_for_run_completion(thread_id, run_id):
    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run.status == 'completed':
            return
        elif run.status == 'failed':
            raise Exception("Run failed")
        time.sleep(1)

def get_assistant_response(thread_id):
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    return messages.data[0].content[0].text.value

def generate_new_persona():
    """Generate a new persona using OpenAI assistant"""
    try:
        thread = client.beta.threads.create()
        
        prompt = "Generate a random funny persona for Chubby Wubby. Make it unique and entertaining."
        
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )
        
        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=PERSONA_ASSISTANT_ID
        )
        
        wait_for_run_completion(thread.id, run.id)
        persona = get_assistant_response(thread.id)
        
        return {
            "persona": persona,
            "generated_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error generating new persona: {e}")
        return None

def save_personas(personas):
    """Save personas to cache file"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(personas, f, indent=2)
        logger.info(f"Successfully saved personas to cache: {CACHE_FILE}")
    except Exception as e:
        logger.error(f"Error saving personas: {e}")

def load_personas():
    """Load personas from cache file"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        return {"personas": []}
    except Exception as e:
        logger.error(f"Error loading personas: {e}")
        return {"personas": []}

def check_similarity(new_persona, existing_personas, threshold=0.5):
    """Check if new persona is too similar to existing ones"""
    for persona in existing_personas:
        similarity = SequenceMatcher(
            None, 
            new_persona["persona"].lower(), 
            persona["persona"].lower()
        ).ratio()
        if similarity > threshold:
            return True
    return False

def update_persona_cache():
    """Generate a new persona and update the cache"""
    try:
        logger.info("Generating new persona...")
        max_attempts = 3
        
        for attempt in range(max_attempts):
            new_persona = generate_new_persona()
            
            if new_persona and "persona" in new_persona:
                personas_data = load_personas()
                
                # Check if new persona is too similar to existing ones
                if check_similarity(new_persona, personas_data["personas"]):
                    logger.warning(f"Generated persona too similar to existing ones. Attempt {attempt + 1}/{max_attempts}")
                    continue
                
                logger.info(f"""
                ====== NEW PERSONA GENERATED ======
                Content: {new_persona['persona'][:200]}...
                Generated at: {new_persona['generated_at']}
                ================================
                """)
                
                personas_data["personas"].append(new_persona)
                
                # Keep only the last 5 personas
                if len(personas_data["personas"]) > 5:
                    personas_data["personas"] = personas_data["personas"][-5:]
                
                save_personas(personas_data)
                logger.info(f"Successfully updated persona cache. Total personas: {len(personas_data['personas'])}")
                return
                
        logger.error("Failed to generate unique persona after maximum attempts")
            
    except Exception as e:
        logger.error(f"Error updating persona cache: {e}")

def run_scheduler():
    """Run the scheduler to update personas every 15 minutes"""
    logger.info("Initializing persona cache scheduler...")
    
    # Generate initial persona if cache is empty
    if not os.path.exists(CACHE_FILE):
        logger.info("No cache file found. Generating initial persona...")
        update_persona_cache()
    else:
        logger.info("Existing cache file found. Loading personas...")
        current_personas = load_personas()
        logger.info(f"Currently cached personas: {len(current_personas.get('personas', []))}")
    
    # Schedule the updates
    schedule.every(15).minutes.do(update_persona_cache)
    
    logger.info("Scheduler started. Will generate new persona every 15 minutes.")
    logger.info("Press Ctrl+C to stop the program.")
    
    try:
        while True:
            next_run = schedule.next_run()
            if next_run:
                logger.info(f"Next persona generation scheduled for: {next_run}")
            
            schedule.run_pending()
            time.sleep(60)  # Check every minute instead of every second
            
    except KeyboardInterrupt:
        logger.info("Shutting down persona cache generator...")
        return

if __name__ == "__main__":
    logger.info(f"Starting persona cache generator... Cache will be saved to: {CACHE_FILE}")
    
    # Generate one persona immediately when starting
    logger.info("Generating initial persona...")
    update_persona_cache()
    
    # Then start the scheduler
    run_scheduler() 