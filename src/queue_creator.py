-#=============================================================================
-# Copyright (c) 2025, Seventh State
-#=============================================================================
-# Handles the creation of a new (migrated) queue. It first retrieves the original
-# queue’s settings from the RabbitMQ API and then adjusts its configuration to
-# meet the requirements of the target queue type (either “quorum” or “stream”).
-# It removes settings that aren’t supported by the new type and adds defaults as
-# needed. Finally, it makes an API call to create the new queue with the updated
-# settings.
import requests
import argparse
from config.config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS

def get_queue_settings(vhost, queue_name):
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"

    try:
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()
        queue_data = response.json()

        arguments = queue_data.get("arguments", {})

        return {
            "durable": queue_data.get("durable", True),
            "arguments": arguments
        }

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching queue settings: {e}")
        return None

def create_queue(vhost, queue_name, queue_type, original_settings):
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"
    headers = {"Content-Type": "application/json"}

    new_arguments = original_settings["arguments"].copy()

    if queue_type == "quorum":
        new_arguments["x-queue-type"] = "quorum"

        unsupported_keys = ["exclusive", "auto-delete", "x-max-priority", "master-locator", "version"]
        for key in unsupported_keys:
            new_arguments.pop(key, None)

        new_arguments.setdefault("queue-initial-cluster-size", 3)
        new_arguments.setdefault("leader-locator", "client-local")

    elif queue_type == "stream":
        new_arguments["x-queue-type"] = "stream"

        unsupported_keys = [
            "x-dead-letter-exchange", "x-dead-letter-routing-key",
            "x-single-active-consumer", "overflow_behavior", "x-message-ttl",
            "x-max-length", "x-max-length-bytes"
        ]
        for key in unsupported_keys:
            new_arguments.pop(key, None)

        new_arguments["max-segment-size-bytes"] = 10485760  # 10 MB
        new_arguments["max-time-retention"] = 86400000  # 24 hours

    else:
        print(f"❌ Unsupported queue type: {queue_type}")
        return

    data = {
        "durable": original_settings["durable"],
        "arguments": new_arguments
    }

    response = requests.put(url, auth=(RABBITMQ_USER, RABBITMQ_PASS), json=data, headers=headers)
    if response.status_code in [201, 204]:
        print(f"✅ {queue_type.capitalize()} '{queue_name}' created successfully.")
    else:
        print(f"❌ Failed to create {queue_type.capitalize()} '{queue_name}': {response.text}")

def migrate_queue(vhost, queue_name, target_type, custom_name=None):
    """Migrate a queue by uplifting settings and creating a new queue with a renamed name."""
    print(f"Migrating '{queue_name}' to {target_type}...")

    original_settings = get_queue_settings(vhost, queue_name)
    if not original_settings:
        print(f"❌ Failed to fetch settings for queue '{queue_name}'. Skipping migration.")
        return

    # Determine the new queue name
    if custom_name:
        new_queue_name = custom_name
    else:
        new_queue_name = f"{queue_name}_qq_migrated" if target_type == "quorum" else f"{queue_name}_stream_migrated"

    print(f"🔄 Creating new queue: '{new_queue_name}'")

    create_queue(vhost, new_queue_name, target_type, original_settings)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RabbitMQ Queue Migration Tool")
    parser.add_argument("--vhost", required=True, help="Specify the vHost of the queue")
    parser.add_argument("--queue", required=True, help="Specify the name of the queue to migrate")
    parser.add_argument("--type", required=True, choices=["quorum", "stream"], help="Specify the target queue type")
    parser.add_argument("--custom-name", help="Specify a custom name for the new queue")

    args = parser.parse_args()

    migrate_queue(args.vhost, args.queue, args.type, args.custom_name)
