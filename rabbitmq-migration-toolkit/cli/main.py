import requests
import json
import os
import argparse

# Load environment variables (RabbitMQ credentials)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "http://localhost:15672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

def list_queues(queue_name=None, vhost=None, json_output=False):
    """Fetch and display RabbitMQ queue details with filtering."""
    url = f"{RABBITMQ_HOST}/api/queues"
    if vhost:
        url = f"{RABBITMQ_HOST}/api/queues/{vhost}"

    try:
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()

        queues = response.json()
        if not queues:
            print("🔹 No queues found.")
            return

        # Apply name filter
        if queue_name:
            queues = [q for q in queues if queue_name in q.get("name", "")]

        if json_output:
            print(json.dumps(queues, indent=2))
            return

        # Print formatted table
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
    parser = argparse.ArgumentParser(description="List RabbitMQ Queues")
    parser.add_argument("--name", help="Filter queues by name")
    parser.add_argument("--vhost", help="Filter queues by vhost")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()
    list_queues(queue_name=args.name, vhost=args.vhost, json_output=args.json)
