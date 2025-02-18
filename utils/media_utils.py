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
    """Generate art by randomly selecting traits."""
    try:
        logger.info("Starting art generation...")
        
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

        # Randomly select traits for each category
        selected_traits = {}
        for category in trait_categories:
            if category in available_traits:
                selected_traits[category] = random.choice(available_traits[category])
                logger.info(f"Selected {category}: {selected_traits[category]}")

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
