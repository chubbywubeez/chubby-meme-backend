import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_setup():
    # Required directories
    required_dirs = [
        'output',
        'media/fonts'
    ]
    
    # Required files
    required_files = [
        'media/fonts/Hogfish DEMO.otf',
        'media/fonts/seguiemj.ttf',
        '.env'
    ]
    
    # Check directories
    print("\nChecking directories...")
    for dir_path in required_dirs:
        exists = os.path.exists(dir_path)
        print(f"{dir_path}: {'✓' if exists else '✗'}")
        if not exists:
            os.makedirs(dir_path)
            print(f"Created directory: {dir_path}")
            
    # Check files
    print("\nChecking files...")
    for file_path in required_files:
        exists = os.path.exists(file_path)
        print(f"{file_path}: {'✓' if exists else '✗'}")

if __name__ == "__main__":
    check_setup() 