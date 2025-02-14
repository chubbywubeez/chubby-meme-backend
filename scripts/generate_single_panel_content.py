import logging
import time
from openai import OpenAI
from dotenv import load_dotenv
import os
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

# Content generation assistant ID
CONTENT_ASSISTANT_ID = "asst_wlN7vykmHXMOMiV0z01l2Nk1"

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

def generate_meme_content(prompt, char_limit=75, allow_emojis=False):
    """Generate meme content based on the user's prompt"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Generating meme content (attempt {attempt + 1}/{max_retries})")
            thread = client.beta.threads.create()
            
            # Create a single comprehensive prompt
            emoji_instruction = "with 1-2 emojis not always placed at the end of sentence" if allow_emojis else "without emojis"
            system_prompt = f"""You are a witty meme generator that creates funny, engaging, and relatable content.
            Create a complete, funny comment ({char_limit} chars max) {emoji_instruction} about: {prompt}
            
            Guidelines:
            - Be creative and original
            - Use humor that's appropriate for a general audience
            - Keep it concise and punchy
            - Make it relatable and shareable
            - Stay within {char_limit} characters
            - Focus on making people laugh
            """
            
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=system_prompt
            )
            
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=CONTENT_ASSISTANT_ID
            )
            
            if not wait_for_run_completion(thread.id, run.id):
                if attempt < max_retries - 1:
                    logger.warning(f"Content generation failed, retrying... ({attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return "Having a creative moment..." + (" 😅" if allow_emojis else "")
                
            response = get_assistant_response(thread.id)
            if not response:
                continue
                
            # If response is too long, retry with a more explicit instruction
            if len(response) > char_limit:
                logger.warning(f"Response too long ({len(response)} chars). Retrying with clearer instruction...")
                client.beta.threads.messages.create(
                    thread_id=thread.id,
                    role="user",
                    content=f"That was too long. Write a shorter, complete sentence. Must be {char_limit} chars or less while keeping the humor."
                )
                
                run = client.beta.threads.runs.create(
                    thread_id=thread.id,
                    assistant_id=CONTENT_ASSISTANT_ID
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
                return "Having a creative moment..." + (" 😅" if allow_emojis else "")
            time.sleep(2 ** attempt)  # Exponential backoff
