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

# Initialize OpenAI client with error handling
try:
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        timeout=60.0  # Increase timeout to 60 seconds
    )
    logger.info("Successfully initialized OpenAI client")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    raise

# Update with your actual assistant IDs
PERSONA_ASSISTANT_ID = "asst_mdB3xM0OczHqAKOB3EBrcp72"
THEME_ASSISTANT_ID = "asst_KpVt3IbaX91ccQw8jVexfXff"
CONTENT_ASSISTANT_ID = "asst_l4e1LATSvjLO7DsG8V7X8Q50"

def wait_for_run_completion(thread_id, run_id):
    try:
        max_retries = 30  # 30 seconds max wait
        retry_count = 0
        while retry_count < max_retries:
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run.status == 'completed':
                return True
            elif run.status == 'failed':
                logger.error(f"Run failed with status: {run.status}")
                return False
            elif run.status == 'expired':
                logger.error("Run expired")
                return False
            time.sleep(1)
            retry_count += 1
        logger.error("Run timed out")
        return False
    except Exception as e:
        logger.error(f"Error in wait_for_run_completion: {str(e)}")
        return False

def get_assistant_response(thread_id):
    try:
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        if not messages.data:
            logger.error("No messages found in thread")
            return None
        return messages.data[0].content[0].text.value
    except Exception as e:
        logger.error(f"Error getting assistant response: {str(e)}")
        return None

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
            logger.info(f"Generating theme (attempt {attempt + 1}/{max_retries})")
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
            
            if not wait_for_run_completion(thread.id, run.id):
                if attempt < max_retries - 1:
                    logger.warning(f"Theme generation failed, retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return f"Chubby Wubby reacts to {theme_prompt}"
                
            response = get_assistant_response(thread.id)
            if response:
                return response
                
        except Exception as e:
            logger.error(f"Theme generation attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                return f"Chubby Wubby reacts to {theme_prompt}"
            time.sleep(2 ** attempt)  # Exponential backoff

def generate_content(persona, theme, content_assistant_id, char_limit=75, allow_emojis=False):
    """Generate the final meme content based on persona and theme"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Generating content (attempt {attempt + 1}/{max_retries})")
            thread = client.beta.threads.create()
            
            # First message to establish persona context
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"You are using this persona: {persona[:200]}..."
            )
            
            # Second message for content generation
            emoji_instruction = "with 1-2 emojis not always placed at the end of sentence" if allow_emojis else "do not include emojis"
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"Create a complete, funny comment ({char_limit} chars max) {emoji_instruction} about: {theme[:100]}"
            )
            
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=content_assistant_id
            )
            
            if not wait_for_run_completion(thread.id, run.id):
                if attempt < max_retries - 1:
                    logger.warning(f"Content generation failed, retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return "Chubby Wubby is having a moment..." + (" 😅" if allow_emojis else "")
                
            response = get_assistant_response(thread.id)
            if not response:
                continue
                
            # If response is too long, retry with a more explicit instruction
            if len(response) > char_limit:
                logger.warning(f"Response too long ({len(response)} chars). Retrying with clearer instruction...")
                client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=f"Write a shorter, complete sentence. Must be {char_limit} chars or less while keeping the punchline."
                )
                
                run = client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=content_assistant_id
                )
                
                if not wait_for_run_completion(thread.id, run.id):
                    continue
                    
                response = get_assistant_response(thread.id)
                if not response:
                    continue
            
            # If we still have a too-long response, start a new attempt
            if len(response) > char_limit:
                continue
                
            return response
            
        except Exception as e:
            logger.error(f"Content generation attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                return "Chubby Wubby is having a moment..." + (" 😅" if allow_emojis else "")
            time.sleep(2 ** attempt)  # Exponential backoff
