import requests
import json
import os

# Load environment variables (for RabbitMQ credentials)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "http://localhost:15672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

def list_queues():
    """Fetch and display RabbitMQ queue details."""
    url = f"{RABBITMQ_HOST}/api/queues"
    try:
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()  # Raise error for HTTP issues

        queues = response.json()
        if not queues:
            print("🔹 No queues found.")
            return

        print(f"{'Queue Name':<20}{'Messages':<10}{'State':<15}{'Policies':<10}{'Arguments'}")
        print("=" * 80)

        for queue in queues:
            name = queue.get("name", "N/A")
            messages = queue.get("messages", 0)
            state = queue.get("state", "unknown")
            policies = queue.get("policy", "None")
            arguments = queue.get("arguments", {})

            print(f"{name:<20}{messages:<10}{state:<15}{policies:<10}{json.dumps(arguments)}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching queue details: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list-queues":
        list_queues()
