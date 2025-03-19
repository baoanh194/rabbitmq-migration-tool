#!/usr/bin/env python3
# =============================================================================
# Copyright (c) 2025, Seventh State
# =============================================================================
# Handles the creation of a new (migrated) queue. It first retrieves the original
# queue’s settings from the RabbitMQ API and then adjusts its configuration to
# meet the requirements of the target queue type (either “quorum” or “stream”).
# It removes settings that aren’t supported by the new type and adds defaults as
# needed. Finally, it makes an API call to create the new queue with the updated
# settings.

import argparse
import requests
from config.config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS

API_HEADERS = {"Content-Type": "application/json"}
MESSAGE_BATCH_SIZE = 1000

def _api_request(method, url, auth, headers=None, json=None):
    """Handles API requests with error handling."""
    try:
        response = requests.request(method, url, auth=auth, headers=headers, json=json)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {e}")
        return None

def get_queue_settings(vhost, queue_name):
    """Retrieves queue settings from RabbitMQ API."""
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"
    response = _api_request("GET", url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
    if response:
        queue_data = response.json()
        return {"durable": queue_data.get("durable", True), "arguments": queue_data.get("arguments", {})}
    return None

def create_queue(vhost, queue_name, queue_type, original_settings):
    """Creates a new queue with specified settings."""
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"
    new_arguments = original_settings["arguments"].copy()

    if queue_type == "quorum":
        new_arguments["x-queue-type"] = "quorum"
        _remove_keys(new_arguments, ["exclusive", "auto-delete", "x-max-priority", "master-locator", "version"])
        new_arguments.setdefault("queue-initial-cluster-size", 3)
        new_arguments.setdefault("leader-locator", "client-local")
    elif queue_type == "stream":
        new_arguments["x-queue-type"] = "stream"
        _remove_keys(
            new_arguments,
            [
                "x-dead-letter-exchange",
                "x-dead-letter-routing-key",
                "x-single-active-consumer",
                "overflow_behavior",
                "x-message-ttl",
                "x-max-length",
                "x-max-length-bytes",
            ],
        )
        new_arguments["max-segment-size-bytes"] = 10485760  # 10 MB
        new_arguments["max-time-retention"] = 86400000  # 24 hours
    else:
        print(f"❌ Unsupported queue type: {queue_type}")
        return

    data = {"durable": original_settings["durable"], "arguments": new_arguments}
    response = _api_request("PUT", url, auth=(RABBITMQ_USER, RABBITMQ_PASS), headers=API_HEADERS, json=data)

    if response and response.status_code in [201, 204]:
        print(f"✅ {queue_type.capitalize()} queue '{queue_name}' created successfully.")
    else:
        print(f"❌ Failed to create {queue_type.capitalize()} queue '{queue_name}': {response.text if response else 'Unknown error'}")

def _remove_keys(dictionary, keys):
    """Removes keys from a dictionary if they exist."""
    for key in keys:
        dictionary.pop(key, None)

def move_messages(source_vhost, source_queue, target_queue):
    """Moves messages from source_queue to target_queue."""
    url = f"{RABBITMQ_HOST}/api/queues/{source_vhost}/{source_queue}/get"
    get_body = {
        "count": MESSAGE_BATCH_SIZE,
        "requeue": False,
        "encoding": "auto",
        "ackmode": "ack_requeue_false",
    }

    response = _api_request("POST", url, auth=(RABBITMQ_USER, RABBITMQ_PASS), headers=API_HEADERS, json=get_body)
    if response:
        messages = response.json()
        for message in messages:
            publish_message(target_queue, message)
        print(f"✅ Successfully moved {len(messages)} messages from '{source_queue}' to '{target_queue}'")
    else:
        print(f"❌ Error fetching messages from '{source_queue}': {response.text if response else 'Unknown error'}")

def publish_message(queue_name, message):
    """Publishes a message to a queue."""
    url = f"{RABBITMQ_HOST}/api/exchanges/%2F/amq.default/publish"
    post_body = {
        "properties": message["properties"],
        "routing_key": queue_name,
        "payload": message["payload"],
        "payload_encoding": "string",
    }

    response = _api_request("POST", url, auth=(RABBITMQ_USER, RABBITMQ_PASS), headers=API_HEADERS, json=post_body)
    if not response or response.status_code != 200:
        print(f"❌ Error publishing message to '{queue_name}': {response.text if response else 'Unknown error'}")

def delete_queue(vhost, queue_name):
    """Deletes a queue."""
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"
    response = _api_request("DELETE", url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
    if response and response.status_code in [200, 204]:
        print(f"✅ Queue '{queue_name}' deleted successfully.")
    else:
        print(f"❌ Error deleting queue '{queue_name}': {response.text if response else 'Unknown error'}")

def migrate_queue(vhost, queue_name, target_type):
    """Migrates a queue to a new type."""
    print(f"Starting migration of '{queue_name}' to {target_type}...")

    original_settings = get_queue_settings(vhost, queue_name)
    if not original_settings:
        print(f"❌ Failed to fetch settings for queue '{queue_name}'. Skipping migration.")
        return

    temp_queue_name = f"{queue_name}_temp_migrated"

    print(f"Creating temporary queue '{temp_queue_name}'")
    create_queue(vhost, temp_queue_name, "quorum", original_settings)

    print(f"Moving messages from '{queue_name}' to '{temp_queue_name}'")
    move_messages(vhost, queue_name, temp_queue_name)

    print(f"Deleting original queue '{queue_name}'")
    delete_queue(vhost, queue_name)

    print(f"Recreating '{queue_name}' as {target_type}")
    create_queue(vhost, queue_name, target_type, original_settings)

    print(f"Moving messages back to '{queue_name}'")
    move_messages(vhost, temp_queue_name, queue_name)

    print(f"Deleting temporary queue '{temp_queue_name}'")
    delete_queue(vhost, temp_queue_name)

    print(f"Migration completed! Queue '{queue_name}' is now a {target_type} queue.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RabbitMQ Queue Migration Tool")
    parser.add_argument("--vhost", required=True, help="Specify the vHost of the queue")
    parser.add_argument("--queue", required=True, help="Specify the name of the queue to migrate")
    parser.add_argument("--type", required=True, choices=["quorum", "stream"], help="Specify the target queue type")

    args = parser.parse_args()
    migrate_queue(args.vhost, args.queue, args.type)