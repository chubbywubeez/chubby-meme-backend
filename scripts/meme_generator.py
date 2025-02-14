from PIL import Image, ImageDraw, ImageFont
import os
import textwrap
import logging
import sys
from fastapi import HTTPException
import json
import time  # Add time import

# Add the backend directory to Python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BACKEND_DIR)

# Now we can import our modules
from scripts.generate_single_panel_content import generate_meme_content
from utils.media_utils import get_generated_art

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)


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
        start_time = time.time()
        logger.info(f"""
        ====== Starting Meme Generation ======
        Prompt: {theme_prompt}
        Char Limit: {char_limit}
        Allow Emojis: {allow_emojis}
        Start Time: {time.time()}
        ===================================
        """)
        
        # Generate art first
        logger.info("Starting art generation...")
        try:
            art_start_time = time.time()
            image_path, metadata_traits = get_generated_art(
                output_path="output/generated_art.png", 
                return_metadata=True,
                persona_prompt=persona_prompt,
                theme_prompt=theme_prompt
            )
            art_duration = time.time() - art_start_time
            logger.info(f"Art generation successful: {image_path} (took {art_duration:.2f} seconds)")
        except Exception as e:
            logger.error(f"Art generation failed after {time.time() - art_start_time:.2f} seconds: {type(e).__name__} - {str(e)}", exc_info=True)
            raise

        # Generate meme content
        logger.info("Starting content generation...")
        try:
            content_start_time = time.time()
            meme_content = generate_meme_content(
                prompt=theme_prompt,
                char_limit=char_limit,
                allow_emojis=allow_emojis
            )
            content_duration = time.time() - content_start_time
            logger.info(f"Content generation successful (took {content_duration:.2f} seconds)")
        except Exception as e:
            logger.error(f"Content generation failed after {time.time() - content_start_time:.2f} seconds: {type(e).__name__} - {str(e)}", exc_info=True)
            raise

        # Create the image
        logger.info("Starting image creation with text...")
        try:
            text_start_time = time.time()
            final_image = add_text_to_image(image_path, meme_content, allow_emojis=allow_emojis)
            text_duration = time.time() - text_start_time
            total_duration = time.time() - start_time
            logger.info(f"""
            ====== Meme Generation Complete ======
            Total Duration: {total_duration:.2f} seconds
            - Art Generation: {art_duration:.2f} seconds
            - Content Generation: {content_duration:.2f} seconds
            - Text Addition: {text_duration:.2f} seconds
            ===================================
            """)
            return final_image
        except Exception as e:
            logger.error(f"Image creation failed after {time.time() - text_start_time:.2f} seconds: {type(e).__name__} - {str(e)}", exc_info=True)
            raise

    except Exception as e:
        total_duration = time.time() - start_time
        logger.error(f"""
        ====== ERROR IN SIMULATE_TWEET ======
        Error type: {type(e).__name__}
        Error message: {str(e)}
        Total Duration Before Error: {total_duration:.2f} seconds
        Prompt: {theme_prompt}
        ================================
        """, exc_info=True)
        raise


if __name__ == "__main__":
    simulate_tweet()
