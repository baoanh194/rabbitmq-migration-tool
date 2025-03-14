import logging

logging.basicConfig(
    filename="migration_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log_info(message):
    logging.info(message)

def log_error(message):
    logging.error(message)
