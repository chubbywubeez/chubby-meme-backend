from PIL import Image, ImageDraw, ImageFont
import os
import textwrap
import logging
import sys

# Add the backend directory to Python path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BACKEND_DIR)

# Now we can import our modules
from scripts.generate_two_panel_meme_content import generate_content
from utils.two_panel_image_utils import generate_two_panel_images

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Assistant IDs
PERSONA_ASSISTANT_ID = "asst_mdB3xM0OczHqAKOB3EBrcp72"
THEME_ASSISTANT_ID = "asst_KpVt3IbaX91ccQw8jVexfXff"
CONTENT_ASSISTANT_ID = "asst_l4e1LATSvjLO7DsG8V7X8Q50"

def is_emoji(char):
    """Better emoji detection"""
    return any([
        '\U0001F300' <= char <= '\U0001F9FF',  # Miscellaneous Symbols and Pictographs
        '\U0001F600' <= char <= '\U0001F64F',  # Emoticons
        '\U0001F680' <= char <= '\U0001F6FF',  # Transport and Map Symbols
        '\U0001F900' <= char <= '\U0001F9FF',  # Supplemental Symbols and Pictographs
        '\u2600' <= char <= '\u26FF',          # Miscellaneous Symbols
        '\u2700' <= char <= '\u27BF'           # Dingbats
    ])

def calculate_text_height(text, primary_font, emoji_font, panel_width, text_padding, line_spacing):
    """Calculate the height needed for text without drawing it"""
    # Calculate approximate character width for text wrapping
    avg_char_width = primary_font.getbbox("A")[2]
    wrapped_text = textwrap.fill(text, width=int(panel_width / avg_char_width))
    text_lines = wrapped_text.split("\n")
    
    total_height = 0
    for line in text_lines:
        line_height = max(
            primary_font.getbbox(line)[3],
            emoji_font.getbbox(line)[3] if any(is_emoji(c) for c in line) else 0
        )
        total_height += line_height + line_spacing
    
    return total_height - line_spacing + (2 * text_padding)

def create_panel(image_path, text, font_path, emoji_font_path, panel_width=600, text_padding=20, fixed_text_height=None):
    """Create a single panel with text and image"""
    try:
        # Load fonts
        primary_font = ImageFont.truetype(font_path, size=55)
        emoji_font = ImageFont.truetype(emoji_font_path, size=48)
        line_spacing = 40
        
        # Load the image
        image = Image.open(image_path).convert("RGBA")
        
        # Calculate or use fixed text height
        if fixed_text_height is None:
            text_height = calculate_text_height(text, primary_font, emoji_font, panel_width, text_padding, line_spacing)
        else:
            text_height = fixed_text_height

        # Create panel with calculated dimensions
        panel_height = text_height + image.height + (2 * text_padding)
        panel = Image.new("RGBA", (panel_width, panel_height), (255, 255, 255, 255))
        
        # Load and resize the image to fit panel width while maintaining aspect ratio
        aspect_ratio = image.height / image.width
        panel_height = int(panel_width * aspect_ratio)
        image = image.resize((panel_width, panel_height), Image.Resampling.LANCZOS)
        
        # Load fonts
        primary_font = ImageFont.truetype(font_path, size=40)
        emoji_font = ImageFont.truetype(emoji_font_path, size=36)  # Slightly smaller for better proportions
        
        # Calculate text height
        draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        wrapped_text = textwrap.fill(text, width=30)
        text_lines = wrapped_text.split('\n')
        line_spacing = 16
        
        # Calculate total text height
        text_height = 0
        for line in text_lines:
            line_height = max(
                primary_font.getbbox(line)[3],
                emoji_font.getbbox(line)[3] if any(is_emoji(c) for c in line) else 0
            )
            text_height += line_height + line_spacing
        text_height -= line_spacing  # Remove extra spacing after last line
        
        # Create panel with space for text
        total_height = text_height + (2 * text_padding) + panel_height
        panel = Image.new("RGBA", (panel_width, total_height), (255, 255, 255, 255))
        
        # Add text with improved emoji support
        draw = ImageDraw.Draw(panel)
        y = text_padding
        
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
            start_x = (panel_width - line_width) // 2
            
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
        
        # Add image below text
        panel.paste(image, (0, text_height + (2 * text_padding)))
        
        return panel
        
    except Exception as e:
        logger.error(f"Error creating panel: {e}")
        raise

def create_meme(persona_prompt="", theme_prompt="", char_limit=75, allow_emojis=False):
    """Main function to create a complete two-panel meme"""
    try:
        # Step 1: Generate both images with consistent traits except mouth and eyes
        logger.info("Generating setup and punchline images...")
        setup_image, punchline_image, metadata = generate_two_panel_images(
            setup_path="output/setup_art.png",
            punchline_path="output/punchline_art.png",
            return_metadata=True,
            persona_prompt=persona_prompt,  # Pass persona prompt for body/head
            theme_prompt=theme_prompt      # Pass theme prompt for eyes/mouth
        )
        
        # Step 2: Generate the text based on the metadata
        logger.info("Generating meme text based on metadata...")
        
        # Separate metadata for setup and punchline panels
        setup_metadata = {k: v for k, v in metadata.items() 
                         if not k.startswith('punchline_')}
        punchline_metadata = {
            **setup_metadata,
            'mouth': metadata['punchline_mouth'],
            'eyes': metadata['punchline_eyes']
        }
        
        response = generate_content(
            persona_prompt=persona_prompt,
            theme_prompt=theme_prompt,
            setup_metadata=setup_metadata,
            punchline_metadata=punchline_metadata,
            persona_assistant_id=PERSONA_ASSISTANT_ID,
            theme_assistant_id=THEME_ASSISTANT_ID,
            content_assistant_id=CONTENT_ASSISTANT_ID,
            char_limit=char_limit,
            allow_emojis=allow_emojis
        )
        
        setup_text, punchline_text = response.split('|')
        setup_text = setup_text.strip()
        punchline_text = punchline_text.strip()
        
        logger.info(f"Generated setup: {setup_text}")
        logger.info(f"Generated punchline: {punchline_text}")
        
        # Step 3: Create the final meme
        font_path = "media/fonts/Hogfish DEMO.otf"
        emoji_font_path = "media/fonts/seguiemj.ttf"
        
        # Panel configuration
        panel_width = 600
        panel_margin = 40  # Add this back
        text_padding = 20
        
        primary_font = ImageFont.truetype(font_path, size=55)
        emoji_font = ImageFont.truetype(emoji_font_path, size=48)
        line_spacing = 40
        
        setup_text_height = calculate_text_height(
            setup_text, primary_font, emoji_font, panel_width, text_padding, line_spacing
        )
        punchline_text_height = calculate_text_height(
            punchline_text, primary_font, emoji_font, panel_width, text_padding, line_spacing
        )
        
        # Use the larger height for both panels
        fixed_text_height = max(setup_text_height, punchline_text_height)
        
        # Create both panels with fixed text height
        left_panel = create_panel(
            setup_image, setup_text, font_path, emoji_font_path, 
            panel_width, text_padding, fixed_text_height
        )
        right_panel = create_panel(
            punchline_image, punchline_text, font_path, emoji_font_path, 
            panel_width, text_padding, fixed_text_height
        )
        
        # Calculate total image dimensions
        total_width = (panel_width * 2) + (panel_margin * 3)
        total_height = max(left_panel.height, right_panel.height) + (panel_margin * 2)
        
        # Resize the background image to fit the final dimensions
        background_image_path = "media/assets/background/Orange.png"  # Update with the actual path
        background_image = Image.open(background_image_path).convert("RGBA")
        background_image = background_image.resize((total_width, total_height), Image.Resampling.LANCZOS)
        
        # Create the final image
        final_image = Image.new("RGBA", (total_width, total_height))
        final_image.paste(background_image, (0, 0))
        
        # Add white border to panels
        left_panel_with_border = Image.new("RGBA", (left_panel.width + 4, left_panel.height + 4), (255, 255, 255, 255))
        right_panel_with_border = Image.new("RGBA", (right_panel.width + 4, right_panel.height + 4), (255, 255, 255, 255))
        
        left_panel_with_border.paste(left_panel, (2, 2))
        right_panel_with_border.paste(right_panel, (2, 2))
        
        # Paste panels with margin
        final_image.paste(left_panel_with_border, (panel_margin, panel_margin), left_panel_with_border)
        final_image.paste(right_panel_with_border, (panel_width + (panel_margin * 2), panel_margin), right_panel_with_border)
        
        # Instead of saving, return the image object
        logger.info("Meme created successfully")
        return final_image
        
    except Exception as e:
        logger.error(f"Error in meme creation: {e}")
        raise

if __name__ == "__main__":
    create_meme() 