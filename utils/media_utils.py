import os
import random
from PIL import Image
import logging
import sys
from utils.logger import get_logger

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))
from image_generator_utils import get_generate_art  # Import your art generation function
import requests
from requests_oauthlib import OAuth1

logger = get_logger(__name__)

UPLOAD_MEDIA_URL = "https://upload.twitter.com/1.1/media/upload.json"

import os
import random
from PIL import Image

import os
import random
from PIL import Image

def load_images_from_folder(folder):
    """Load all image files from a folder."""
    return [
        Image.open(os.path.join(folder, file))
        for file in os.listdir(folder)
        if file.endswith('.png')
    ]

def get_generated_art(output_path="output/generated_art.png", return_metadata=False, persona_prompt="", theme_prompt=""):
    """Generate art based on persona and theme prompts."""
    try:
        logger.info(f"Received persona prompt: '{persona_prompt}', theme prompt: '{theme_prompt}'")
        
        ASSETS_PATH = "media/assets"
        trait_categories = ['background', 'base', 'mouth', 'eyes', 'head', 'body']
        
        # Get all available traits
        available_traits = {}
        for category in trait_categories:
            category_path = os.path.join(ASSETS_PATH, category)
            if os.path.exists(category_path):
                traits = [os.path.splitext(f)[0] for f in os.listdir(category_path) if f.endswith('.png')]
                available_traits[category] = traits
                logger.info(f"Found {category} traits: {traits}")

        selected_traits = {}
        
        # Match persona-related traits (body and head)
        persona_keywords = [word.lower() for word in persona_prompt.split()]
        for category in ['body', 'head', 'mouth', 'eyes']:
            for trait in available_traits[category]:
                trait_lower = trait.lower()
                for keyword in persona_keywords:
                    if keyword in trait_lower or trait_lower in keyword:
                        selected_traits[category] = trait
                        logger.info(f"✓ Matched {category}: {trait} from persona keyword '{keyword}'")
                        break

        # Match theme-related traits (eyes and mouth)
        theme_keywords = [word.lower() for word in theme_prompt.split()]
        for category in ['body', 'head', 'eyes', 'mouth']:
            for trait in available_traits[category]:
                trait_lower = trait.lower()
                for keyword in theme_keywords:
                    if keyword in trait_lower or trait_lower in keyword:
                        selected_traits[category] = trait
                        logger.info(f"✓ Matched {category}: {trait} from theme keyword '{keyword}'")
                        break

        # For any category without a match, select random trait
        for category in trait_categories:
            if category not in selected_traits and category in available_traits:
                selected_traits[category] = random.choice(available_traits[category])
                logger.info(f"Randomly selected {category}: {selected_traits[category]}")

        # Generate art with selected traits
        result = get_generate_art(
            output_path=output_path,
            return_metadata=True,
            forced_traits=selected_traits
        )
        
        if return_metadata:
            path, metadata = result
            logger.info(f"Generated art with traits: {metadata}")
            return path, metadata
        return result

    except Exception as e:
        logger.error(f"Error in get_generated_art: {e}")
        raise

def validate_media(media_path):
    """
    Validate that the media file exists and is in a supported format.
    """
    if not os.path.exists(media_path):
        raise FileNotFoundError(f"Media file {media_path} not found.")
    if not media_path.endswith((".jpg", ".jpeg", ".png")):
        raise ValueError(f"Unsupported media format: {media_path}")
    return True

def upload_media(media_path, auth):
    """
    Upload media to Twitter and return the media_id.
    Args:
        media_path (str): Path to the media file.
        auth (OAuth1): OAuth1 authentication object.
    Returns:
        str: The media ID assigned by Twitter.
    """
    files = {"media": open(media_path, "rb")}
    try:
        response = requests.post(UPLOAD_MEDIA_URL, files=files, auth=auth)
        if response.status_code == 200:
            media_id = response.json()["media_id_string"]
            logger.info(f"Media uploaded successfully: {media_id}")
            return media_id
        else:
            logger.error(f"Error uploading media: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"An error occurred while uploading media: {e}")
        return None
