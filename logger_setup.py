import logging
import sys

def setup_logger(log_file="app.log"):
    logger = logging.getLogger("app_logger")
    logger.setLevel(logging.INFO)

    # Create a file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    # Create a stream handler for console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create a formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the file handler and console handler to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
