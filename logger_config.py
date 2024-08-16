import logging

class LoggerConfig:
    @staticmethod
    def get_logger(name, level=logging.INFO, log_file=None):
        """
        Gibt einen Logger mit der zentralen Konfiguration zurück.

        Args:
            name (str): Der Name des Loggers.
            level (int): Das Log-Level (z.B. logging.INFO).
            log_file (str, optional): Pfad zur Log-Datei. Wenn None, wird nur die Konsole verwendet.

        Returns:
            logging.Logger: Der konfigurierte Logger.
        """
        logger = logging.getLogger(name)
        if not logger.hasHandlers():  # Verhindert das Hinzufügen mehrerer Handler bei mehreren Aufrufen
            logger.setLevel(level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

            # Konsole-Handler hinzufügen
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # Optional: Datei-Handler hinzufügen
            if log_file:
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)

        return logger
