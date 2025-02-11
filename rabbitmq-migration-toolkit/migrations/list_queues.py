import requests
import yaml
from config.settings import load_config

def list_queues():
    """Fetch and display all queues from RabbitMQ."""
    config = load_config()
    url = f"http://{config['host']}:{config['port']}/api/queues"
    auth = (config['username'], config['password'])

    try:
        response = requests.get(url, auth=auth, timeout=5)
        response.raise_for_status()
        queues = response.json()

        if not queues:
            print("No queues found.")
            return

        print("\nQueues in RabbitMQ:")
        for queue in queues:
            print(f" - {queue['name']} (Messages: {queue['messages']})")

    except requests.RequestException as e:
        print(f"Error: {e}")
