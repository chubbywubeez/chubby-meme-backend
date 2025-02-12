import logging
import time
from openai import OpenAI
from dotenv import load_dotenv
import os
import random
from utils.logger import get_logger

# Load environment variables
load_dotenv()

# Configure logging
logger = get_logger(__name__)

# Fetch OpenAI API key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API key is not set. Please add it to your .env file.")

# Initialize OpenAI client
client = OpenAI()

# Update with your actual assistant IDs
PERSONA_ASSISTANT_ID = "asst_mdB3xM0OczHqAKOB3EBrcp72"
THEME_ASSISTANT_ID = "asst_KpVt3IbaX91ccQw8jVexfXff"
CONTENT_ASSISTANT_ID = "asst_l4e1LATSvjLO7DsG8V7X8Q50"

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

def determine_response_length(user_message):
    # Convert to lowercase for easier matching
    message = user_message.lower()
    
    # Keywords that suggest short/medium responses
    joke_keywords = ['joke', 'funny', 'pun', 'laugh', 'humor']
    
    # Keywords that suggest long responses
    story_keywords = ['story', 'tell me about', 'what happened', 'adventure']
    
    # Check for joke-related content
    if any(keyword in message for keyword in joke_keywords):
        return random.choice(["0-50", "51-150"])  # Short or medium for jokes
    
    # Check for story-related content
    elif any(keyword in message for keyword in story_keywords):
        return "151-250"  # Long for stories
    
    # Random length for everything else
    else:
        return random.choice(["0-50", "51-150", "151-250"])

def generate_theme(theme_prompt, persona, theme_assistant_id):
    """Generate a theme based on the prompt and persona"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            thread = client.beta.threads.create()
            
            # Determine if it's crypto or non-crypto theme
            is_crypto = any(word in theme_prompt.lower() for word in ['crypto', 'token', 'coin', 'trade', 'hodl', 'moon'])
            theme_type = "crypto" if is_crypto else "non-crypto"
            
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Generate a {theme_type} theme: {theme_prompt[:50]}"
            )
            
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=theme_assistant_id
            )
            wait_for_run_completion(thread.id, run.id)
            return get_assistant_response(thread.id)
            
        except Exception as e:
            logger.error(f"Theme generation attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                return f"Chubby Wubby reacts to {theme_prompt}"
            time.sleep(1)

def generate_content(persona, theme, content_assistant_id, char_limit=75, allow_emojis=False):
    """Generate the final meme content based on persona and theme"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            thread = client.beta.threads.create()
            
            # Combine persona and theme into a single message for efficiency
            emoji_instruction = "with 1-2 emojis not always placed at the end of sentence" if allow_emojis else "do not include emojis"
            prompt = f"""Using this persona: {persona[:200]}...
            
Create a funny, complete comment ({char_limit} chars max) {emoji_instruction} about: {theme}

Remember:
1. Stay within {char_limit} characters
2. Make it funny and engaging
3. Keep the punchline clear and impactful"""
            
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=prompt
            )
            
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=content_assistant_id
            )
            wait_for_run_completion(thread_id=thread.id, run_id=run.id)
            response = get_assistant_response(thread.id)
            
            # Log response details
            logger.info(f"""
            ====== CONTENT RESPONSE ======
            Length: {len(response)}
            Content: {response}
            =============================
            """)
            
            # If response is too long, retry with a shorter instruction
            if len(response) > char_limit:
                logger.warning(f"Response too long ({len(response)} chars). Retrying with shorter instruction...")
                client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=f"Too long. Give me the shortest possible version that's still funny. Max {char_limit} chars."
                )
                run = client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=content_assistant_id
                )
                wait_for_run_completion(thread.id, run.id)
                response = get_assistant_response(thread.id)
            
            # If we still have a too-long response, start a new attempt
            if len(response) > char_limit:
                continue
                
            return response
            
        except Exception as e:
            logger.error(f"Content generation attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                return "Chubby Wubby is having a moment... 😅" if allow_emojis else "Chubby Wubby is having a moment..."
            time.sleep(1)
