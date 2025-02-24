import logging

# Configure logging
logging.basicConfig(filename="migration.log", level=logging.INFO, format="%(asctime)s - %(message)s")

def log_migration(queue_name, status):
    logging.info(f"Queue: {queue_name}, Status: {status}")

log_migration("classic_queue", "Migrated successfully to Quorum Queue")
