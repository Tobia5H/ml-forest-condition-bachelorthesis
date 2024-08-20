import logging
import os
from datetime import datetime

class LoggerConfig:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(LoggerConfig, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def get_logger(name, level=logging.INFO, log_to_file=True):
        """
        Returns a logger with the central configuration.

        Args:
            name (str): The name of the logger.
            level (int): The log level (e.g., logging.INFO).
            log_to_file (bool): Indicates whether to write logs to a file.

        Returns:
            logging.Logger: The configured logger.
        """
        logger = logging.getLogger(name)
        if not logger.hasHandlers():  # Prevents adding multiple handlers on repeated calls
            logger.setLevel(level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

            # Add console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # Optionally add file handler
            if log_to_file:
                # Create the "logs" directory if it doesn't exist
                os.makedirs("logs", exist_ok=True)
                # Create the log filename based on the current date and time
                log_file = os.path.join("logs", datetime.now().strftime("log_%Y-%m-%d_%H-%M-%S.log"))
                
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)

        return logger
