from utils.logger import get_logger

logger = get_logger(__name__)

def test_logging():
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")

if __name__ == "__main__":
    test_logging() 