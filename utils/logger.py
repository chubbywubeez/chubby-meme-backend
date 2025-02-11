import logging

# Configure logging once for the entire application
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    """Get a logger instance with the specified name"""
    return logging.getLogger(name) 