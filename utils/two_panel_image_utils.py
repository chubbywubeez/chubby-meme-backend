import os
import random
from PIL import Image
import logging
from .image_generator_utils import load_images_from_folder



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_two_panel_images(setup_path="output/setup_art.png", 
                            punchline_path="output/punchline_art.png",
                            return_metadata=False,
                            persona_prompt="",
                            theme_prompt=""):
    """
    Generate two related art images for a two-panel meme.
    Uses persona prompt for body/head and theme prompt for eyes/mouth.
    The second image maintains all traits from the first except for mouth and eyes.
    
    Args:
        setup_path (str): Path to save the setup panel image
        punchline_path (str): Path to save the punchline panel image
        return_metadata (bool): Whether to return metadata about the chosen traits
        persona_prompt (str): Prompt to influence trait selection for body/head
        theme_prompt (str): Prompt to influence trait selection for eyes/mouth
    
    Returns:
        tuple: (setup_path, punchline_path, metadata) if return_metadata is True
               (setup_path, punchline_path) if return_metadata is False
    """
    try:
        # Paths to folders
        base_dir = 'media/assets'
        layers = ['background', 'base', 'mouth', 'eyes', 'head', 'body']
        changing_features = ['mouth', 'eyes']
        
        logger.info(f"Received persona prompt: '{persona_prompt}', theme prompt: '{theme_prompt}'")

        # Load images and get available traits
        images = {}
        available_traits = {}
        metadata_traits = {}
        
        for layer in layers:
            layer_path = os.path.join(base_dir, layer)
            images[layer] = load_images_from_folder(layer_path)
            if not images[layer]:
                logger.error(f"No images found for layer: {layer}")
                return None
                
            # Get available trait names
            available_traits[layer] = [
                os.path.splitext(os.path.basename(img.filename))[0] 
                for img in images[layer]
            ]
            logger.info(f"Found {layer} traits: {available_traits[layer]}")

        # Match traits based on persona and theme prompts
        selected_traits = {}
        persona_keywords = [word.lower() for word in persona_prompt.split()]
        theme_keywords = [word.lower() for word in theme_prompt.split()]
        
        # Check each trait for partial matches with any keyword
        for layer in layers:
            if layer in ['body', 'head']:
                for trait in available_traits[layer]:
                    trait_lower = trait.lower()
                    for keyword in persona_keywords:
                        if keyword in trait_lower or trait_lower in keyword:
                            selected_traits[layer] = trait
                            logger.info(f"✓ Matched {layer}: {trait} from persona keyword '{keyword}'")
                            break
            elif layer in ['eyes', 'mouth']:
                for trait in available_traits[layer]:
                    trait_lower = trait.lower()
                    for keyword in theme_keywords:
                        if keyword in trait_lower or trait_lower in keyword:
                            selected_traits[layer] = trait
                            logger.info(f"✓ Matched {layer}: {trait} from theme keyword '{keyword}'")
                            break

        # Select images based on matched traits or random selection
        chosen_images = {}
        for layer in layers:
            if layer in selected_traits:
                # Find the image that matches the selected trait
                matching_images = [
                    img for img in images[layer] 
                    if os.path.splitext(os.path.basename(img.filename))[0] == selected_traits[layer]
                ]
                chosen_images[layer] = matching_images[0]
                logger.info(f"Using matched trait for {layer}: {selected_traits[layer]}")
            else:
                chosen_images[layer] = random.choice(images[layer])
                trait_name = os.path.splitext(os.path.basename(chosen_images[layer].filename))[0]
                logger.info(f"Randomly selected {layer}: {trait_name}")

            # Store metadata about chosen traits
            if layer not in ['background', 'base']:
                trait_name = os.path.splitext(os.path.basename(chosen_images[layer].filename))[0]
                metadata_traits[layer] = trait_name

        # Create setup panel
        setup_image = chosen_images['background']
        for layer in layers[1:]:
            setup_image = Image.alpha_composite(setup_image.convert('RGBA'), 
                                             chosen_images[layer].convert('RGBA'))
        
        # Create punchline panel with different mouth and eyes
        punchline_image = chosen_images['background']
        
        # Select different mouth and eyes for punchline
        for feature in changing_features:
            available_options = [img for img in images[feature] 
                               if img != chosen_images[feature]]
            new_feature = random.choice(available_options)
            chosen_images[feature] = new_feature
            
            # Update metadata for new feature
            new_trait = os.path.splitext(os.path.basename(new_feature.filename))[0]
            metadata_traits[f'punchline_{feature}'] = new_trait
        
        # Compose punchline image
        for layer in layers[1:]:
            punchline_image = Image.alpha_composite(punchline_image.convert('RGBA'), 
                                                  chosen_images[layer].convert('RGBA'))

        # Ensure output directories exist
        os.makedirs(os.path.dirname(setup_path), exist_ok=True)
        os.makedirs(os.path.dirname(punchline_path), exist_ok=True)

        # Save the images
        setup_image.save(setup_path)
        punchline_image.save(punchline_path)
        
        logger.info(f"Successfully generated two-panel images")
        logger.info(f"Setup panel saved to: {setup_path}")
        logger.info(f"Punchline panel saved to: {punchline_path}")
        
        if return_metadata:
            return setup_path, punchline_path, metadata_traits
        return setup_path, punchline_path

    except Exception as e:
        logger.error(f"Error generating two-panel art: {e}")
        return None 