import os
import random
from PIL import Image
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_images_from_folder(folder):
    """Load all images from a directory."""
    try:
        if not os.path.exists(folder):
            logger.error(f"Folder not found: {folder}")
            raise FileNotFoundError(f"Asset folder not found: {folder}")
            
        logger.info(f"Folder exists: {folder}")
        logger.info(f"Folder contents: {os.listdir(folder)}")
            
        images = []
        for file in os.listdir(folder):
            if file.endswith(('.png', '.jpg', '.jpeg')):
                try:
                    image_path = os.path.join(folder, file)
                    logger.info(f"Loading image: {image_path}")
                    image = Image.open(image_path)
                    logger.info(f"Successfully loaded image: {image_path}")
                    images.append(image)
                except Exception as e:
                    logger.error(f"Error loading image {file}: {e}")
                    logger.exception(e)
                    
        if not images:
            raise ValueError(f"No valid images found in {folder}")
            
        logger.info(f"Successfully loaded {len(images)} images from {folder}")
        return images
    except Exception as e:
        logger.error(f"Error loading images from {folder}: {e}")
        logger.exception(e)
        raise

def get_generate_art(output_path="/tmp/generated_art.png", return_metadata=False, forced_traits=None):
    """
    Generate art image using layered images.
    Args:
        output_path (str): Path to save the generated art.
        return_metadata (bool): Whether to return metadata about the chosen traits
        forced_traits (dict): Dictionary of traits to use instead of random selection
    Returns:
        str: Path to the generated art file
        dict (optional): Metadata about the chosen traits if return_metadata is True
    """
    try:
        logger.info(f"Starting art generation with forced traits: {forced_traits}")
        logger.info(f"Starting art generation, output path: {output_path}")
        
        # Get the absolute path to the media directory
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "media/assets")
        logger.info(f"Looking for assets in: {base_dir}")
        
        # Verify base directory exists
        if not os.path.exists(base_dir):
            logger.error(f"Base directory not found: {base_dir}")
            return (None, {}) if return_metadata else None

        # Load images
        images = {}
        metadata_traits = {}
        for layer in ['background', 'base', 'mouth', 'eyes', 'head', 'body']:
            layer_path = os.path.join(base_dir, layer)
            try:
                images[layer] = load_images_from_folder(layer_path)
            except Exception as e:
                logger.error(f"Error loading layer {layer}: {e}")
                return (None, {}) if return_metadata else None

        # Select images based on forced_traits or random selection
        chosen_images = {}
        for layer in images:
            if forced_traits and layer in forced_traits:
                # Find the image that matches the forced trait
                trait_name = forced_traits[layer]
                matching_images = [
                    img for img in images[layer] 
                    if os.path.splitext(os.path.basename(img.filename))[0] == trait_name
                ]
                if matching_images:
                    chosen_images[layer] = matching_images[0]
                    logger.info(f"Using forced trait for {layer}: {trait_name}")
                else:
                    # Fallback to random if trait not found
                    chosen_images[layer] = random.choice(images[layer])
                    logger.info(f"Forced trait {trait_name} not found for {layer}, using random")
            else:
                chosen_images[layer] = random.choice(images[layer])
                logger.info(f"Using random trait for {layer}")

            # Store metadata about chosen traits
            if layer not in ['background', 'base']:
                trait_name = os.path.splitext(os.path.basename(chosen_images[layer].filename))[0]
                metadata_traits[layer] = trait_name

        # Start with the base image
        result_image = chosen_images['background']
        logger.info("Starting image composition")

        # Composite the images in order
        for layer in images:
            result_image = Image.alpha_composite(result_image.convert('RGBA'), 
                                              chosen_images[layer].convert('RGBA'))
            logger.info(f"Composited layer {layer}")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save the result
        result_image.save(output_path)
        logger.info(f"Successfully saved generated art to: {output_path}")
        
        return (output_path, metadata_traits) if return_metadata else output_path
    except Exception as e:
        logger.error(f"Error generating art: {e}")
        logger.exception(e)  # This will log the full stack trace
        return (None, {}) if return_metadata else None

if __name__ == '__main__':
    get_generate_art()
