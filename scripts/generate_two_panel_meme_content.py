import logging
import time
from openai import OpenAI
from dotenv import load_dotenv
import os
import random

# Get the absolute path to the backend directory
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(BACKEND_DIR, ".env")

# Load environment variables from .env file with explicit path
load_dotenv(ENV_PATH)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client with API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError(f"OpenAI API key is not set. Please add it to your .env file at {ENV_PATH}")

# Initialize OpenAI client with the API key
client = OpenAI(api_key=api_key)

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
 
        return random.choice(["30-50"])

def generate_content(persona_prompt, theme_prompt, setup_metadata, punchline_metadata,
                    persona_assistant_id, theme_assistant_id, content_assistant_id,
                    char_limit=75, allow_emojis=False):
    try:
        logger.info(f"""Generating two-panel content:
            allow_emojis: {allow_emojis}
            char_limit: {char_limit}
            persona_length: {len(persona_prompt)}
            theme_length: {len(theme_prompt)}
        """)
        
        emoji_instruction = (
            "Include 1-2 well-placed emojis per panel that emphasize key moments." 
            if allow_emojis 
            else "Do not include any emojis, hashtags, or quotation marks."
        )
        
        # Randomly determine character length for flexibility
        char_size = determine_response_length(persona_prompt)
        logger.info(f"Selected character length: {char_size}")

        # Step 1: Persona Assistant
        thread = client.beta.threads.create()
        logger.info("Step 1: Persona Assistant")
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"""Define the persona for a two-panel meme featuring Chubby Wubby based on this description:
            {persona_prompt}
            
            The first panel, Chubby Wubby has these traits: {setup_metadata}.
            The second panel, Chubby Wubby has these traits: {punchline_metadata}"""
        )
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=persona_assistant_id
        )
        wait_for_run_completion(thread.id, run.id)
        persona_response = get_assistant_response(thread.id)
        logger.info(f"Persona Response: {persona_response}")

        # Step 2: Theme/Angle Assistant
        logger.info("Step 2: Theme Assistant")
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"""Using Chubby Wubby's persona: {persona_response},
            generate a theme and angle for a two-panel meme:
            Using {theme_prompt} as inspiration:
            - Panel 1: Set up a situation, expectation, or challenge inspired by these traits: {setup_metadata}.
            - Panel 2: Deliver a surprising, ironic, or exaggerated resolution inspired by the mouth and eyes changing to these traits: {punchline_metadata}.
            - Make the theme humorous and relatable. Focus on contrasting emotions, universal appeal, or niche relevance.

            '"""
        )
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=theme_assistant_id
        )
        wait_for_run_completion(thread.id, run.id)
        theme_response = get_assistant_response(thread.id)
        logger.info(f"Theme Response: {theme_response}")

        # Step 3: Content Generation Assistant
        logger.info("Step 3: Content Generation Assistant")
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"""Create a two-panel meme with these requirements:
                1. Use Chubby Wubby's persona: {persona_response}
                2. Theme/angle: {theme_response}
                3. Panel 1: Set up a situation or expectation using these traits: {setup_metadata}
                4. Panel 2: Deliver a surprising, ironic, or exaggerated resolution inspired by the mouth and eyes changing to these traits:{punchline_metadata}
                5. Always connect the panels together through the same idea, meme, or funny comment
                6. Return exactly two captions with no additional context or explanation
                7. {emoji_instruction}
                8. Each panel caption should be between {char_limit-15}-{char_limit} characters
                9. Separate the two captions with a single `|` character
                """
        )
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=content_assistant_id
        )
        wait_for_run_completion(thread.id, run.id)
        content_response = get_assistant_response(thread.id)
        logger.info(f"Content Response: {content_response}")

        return content_response

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None


    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None
