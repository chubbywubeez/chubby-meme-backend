from PIL import Image, ImageDraw, ImageFont
import os
import textwrap
import logging
import sys
from fastapi import HTTPException
import random
import json

# Add the backend directory to Python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BACKEND_DIR)

# Now we can import our modules
from scripts.generate_single_panel_content import (
    generate_content, 
    generate_theme
)
from utils.media_utils import get_generated_art
from scripts.persona_cache_generator import load_personas, generate_new_persona

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

# Assistant IDs
PERSONA_ASSISTANT_ID = "asst_mdB3xM0OczHqAKOB3EBrcp72"
THEME_ASSISTANT_ID = "asst_KpVt3IbaX91ccQw8jVexfXff"
CONTENT_ASSISTANT_ID = "asst_l4e1LATSvjLO7DsG8V7X8Q50"


def add_text_to_image(image_path, text, allow_emojis=False, output_path="output/final_tweet.png"):
    """
    Add text to an image with a dedicated box at the top of the image.
    Supports both custom font and emoji rendering.
    """
    try:
        # Load the base image
        image = Image.open(image_path).convert("RGBA")
        image_width, image_height = image.size

        # Set fonts
        primary_font_path = "media/fonts/Hogfish DEMO.otf"
        emoji_font_path = "media/fonts/seguiemj.ttf"
        
        # Verify fonts exist
        if not os.path.exists(primary_font_path):
            raise FileNotFoundError(f"Primary font not found: {primary_font_path}")
        if not os.path.exists(emoji_font_path):
            raise FileNotFoundError(f"Emoji font not found: {emoji_font_path}")
            
        primary_font = ImageFont.truetype(primary_font_path, size=55)
        emoji_font = ImageFont.truetype(emoji_font_path, size=48)  # Slightly smaller for better proportions

        def is_emoji(char):
            """Better emoji detection"""
            if not allow_emojis:
                return False
            return any([
                '\U0001F300' <= char <= '\U0001F9FF',  # Miscellaneous Symbols and Pictographs
                '\U0001F600' <= char <= '\U0001F64F',  # Emoticons
                '\U0001F680' <= char <= '\U0001F6FF',  # Transport and Map Symbols
                '\U0001F900' <= char <= '\U0001F9FF',  # Supplemental Symbols and Pictographs
                '\u2600' <= char <= '\u26FF',          # Miscellaneous Symbols
                '\u2700' <= char <= '\u27BF'           # Dingbats
            ])

        # Create new image with RGBA mode
        margin = 0
        text_padding = 20
        text_margin_top = 20
        max_text_width = image_width - 2 * margin
        
        # Calculate approximate character width for text wrapping
        avg_char_width = primary_font.getbbox("A")[2]
        wrapped_text = textwrap.fill(text, width=int(max_text_width / avg_char_width))

        # Calculate text height and prepare new image
        draw = ImageDraw.Draw(Image.new('RGBA', (1, 1), (0, 0, 0, 0)))
        text_lines = wrapped_text.split("\n")
        line_spacing = 40
        
        # Calculate total height needed
        total_height = 0
        for line in text_lines:
            line_height = max(
                primary_font.getbbox(line)[3],
                emoji_font.getbbox(line)[3] if any(is_emoji(c) for c in line) else 0
            )
            total_height += line_height + line_spacing
        
        text_height = total_height - line_spacing + 20

        # Total box height
        box_height = text_height + 2 * text_padding + text_margin_top

        # Create new image with space for text
        new_image_height = image_height + box_height + margin
        new_image = Image.new("RGBA", (image_width, new_image_height), (255, 255, 255, 255))
        new_image.paste(image, (0, box_height + margin // 2))

        # Draw the text box
        draw = ImageDraw.Draw(new_image)
        box_y_start = margin // 2
        box_y_end = box_y_start + box_height
        draw.rectangle(
            [(margin // 2, box_y_start), (image_width - margin // 2, box_y_end)],
            fill=(255, 255, 255, 255)
        )

        # Draw text with improved emoji support
        y = box_y_start + text_padding + text_margin_top
        for line in text_lines:
            # Calculate total line width for centering
            line_width = 0
            char_positions = []
            
            # First pass: calculate positions
            x = 0
            for char in line:
                is_emoji_char = is_emoji(char)
                font = emoji_font if is_emoji_char else primary_font
                
                # Add extra spacing around emojis
                if is_emoji_char:
                    x += 5  # Add some padding before emoji
                
                char_bbox = font.getbbox(char)
                char_width = char_bbox[2] - char_bbox[0]
                
                if is_emoji_char:
                    char_width += 10  # Add some padding after emoji
                
                char_positions.append((x, char, font, is_emoji_char))
                x += char_width
                line_width += char_width

            # Calculate starting x position for center alignment
            start_x = (image_width - line_width) // 2

            # Second pass: draw characters
            for x_offset, char, font, is_emoji_char in char_positions:
                x = start_x + x_offset
                
                # Draw with embedded color for emojis
                draw.text(
                    (x, y),
                    char,
                    embedded_color=is_emoji_char,  # Enable color emoji support
                    font=font,
                    fill=(0, 0, 0, 255)
                )

            # Move to next line
            y += max(primary_font.getbbox(line)[3], emoji_font.getbbox(line)[3]) + line_spacing

        # Instead of saving and returning path, return the image object
        # new_image.save(output_path, "PNG")
        # return output_path
        return new_image  # Return the PIL Image object directly
    except Exception as e:
        logger.error(f"Error adding text to image: {e}")
        raise


def simulate_tweet(persona_prompt="", theme_prompt="", char_limit=75, allow_emojis=True):
    try:
        logger.info("Starting meme generation")
        
        # Validate and set default prompts
        if not persona_prompt.strip():
            persona_prompt = "a funny internet meme creator"
            logger.info("Using default persona prompt")
            
        if not theme_prompt.strip():
            theme_prompt = "random funny moment in life"
            logger.info("Using default theme prompt")
        
        # Generate art first
        image_path, metadata_traits = get_generated_art(
            output_path="output/generated_art.png", 
            return_metadata=True,
            persona_prompt=persona_prompt,
            theme_prompt=theme_prompt
        )
        
        # Generate content directly using both prompts
        logger.info(f"""
        ====== GENERATING CONTENT ======
        Using persona prompt: {persona_prompt}
        Using theme prompt: {theme_prompt}
        Char limit: {char_limit}
        Allow emojis: {allow_emojis}
        =============================
        """)
        
        tweet_content = generate_content(
            persona=persona_prompt,
            theme=theme_prompt,
            content_assistant_id=CONTENT_ASSISTANT_ID,
            char_limit=char_limit,
            allow_emojis=allow_emojis
        )

        # Create the image
        final_image = add_text_to_image(image_path, tweet_content, allow_emojis=allow_emojis)
        return final_image

    except Exception as e:
        logger.error(f"""
        ====== ERROR IN SIMULATE_TWEET ======
        Error: {str(e)}
        Persona prompt: {persona_prompt}
        Theme prompt: {theme_prompt}
        ================================
        """)
        raise


if __name__ == "__main__":
    simulate_tweet()
