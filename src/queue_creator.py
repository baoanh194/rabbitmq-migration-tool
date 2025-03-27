#!/usr/bin/env python3
# =============================================================================
# Copyright (c) 2025, Seventh State
# =============================================================================
# Handles migration of a queue to a new type (quorum or stream), ensuring all
# settings are compatible. If migration fails due to unsupported settings or
# connection issues, an appropriate error is logged.

import argparse
import requests
from config.config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS

API_HEADERS = {"Content-Type": "application/json"}
MESSAGE_BATCH_SIZE = 1000

# Feature support matrix
UNSUPPORTED_FEATURES = {
    "quorum": [
        "exclusive", "auto-delete", "x-max-priority", "master-locator", "version"
    ],
    "stream": [
        "x-dead-letter-exchange", "x-message-ttl", "x-max-length", "x-max-priority",
        "x-single-active-consumer", "overflow-behavior", "x-max-length-bytes"
    ]
}

#Handles API requests with error handling.
def _api_request(method, url, auth, headers=None, json=None):
    try:
        response = requests.request(method, url, auth=auth, headers=headers, json=json)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return None

#Retrieves queue settings from RabbitMQ API.
def get_queue_settings(vhost, queue_name):

    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"
    response = _api_request("GET", url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
    if response:
        queue_data = response.json()
        return {
            "durable": queue_data.get("durable", True),
            "arguments": queue_data.get("arguments", {})
        }
    return None

#Checks if the queue has unsupported settings for the target type.
def validate_migration(original_settings, queue_type):
    queue_args = original_settings["arguments"]
    unsupported = UNSUPPORTED_FEATURES.get(queue_type, [])
    found_issues = [key for key in queue_args if key in unsupported]

    if found_issues:
        print(f"Migration failed: {queue_type.capitalize()} queues do not support {found_issues}")
        return False
    return True

#Creates a new queue with specified settings and returns success status.
def create_queue(vhost, queue_name, queue_type, original_settings):
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"
    new_arguments = original_settings["arguments"].copy()

    if queue_type == "quorum":
        new_arguments["x-queue-type"] = "quorum"
        _remove_keys(new_arguments, UNSUPPORTED_FEATURES["quorum"])
        new_arguments.setdefault("queue-initial-cluster-size", 3)
        new_arguments.setdefault("leader-locator", "client-local")
    elif queue_type == "stream":
        new_arguments["x-queue-type"] = "stream"
        _remove_keys(new_arguments, UNSUPPORTED_FEATURES["stream"])
        new_arguments["max-segment-size-bytes"] = 10485760  # 10 MB
        new_arguments["max-time-retention"] = 86400000  # 24 hours
    else:
        print(f"Unsupported queue type: {queue_type}")
        return False

    data = {"durable": original_settings["durable"], "arguments": new_arguments}
    response = _api_request("PUT", url, auth=(RABBITMQ_USER, RABBITMQ_PASS), headers=API_HEADERS, json=data)

    if response and response.status_code in [201, 204]:
        print(f"{queue_type.capitalize()} queue '{queue_name}' created successfully.")
        return True
    else:
        print(f"Failed to create {queue_type.capitalize()} queue '{queue_name}': {response.text if response else 'Unknown error'}")
        return False

#Removes keys from a dictionary if they exist
def _remove_keys(dictionary, keys):
    for key in keys:
        dictionary.pop(key, None)

#Migrates a queue from classic to quorum or stream."
def migrate_queue(vhost, queue_name, target_type):
    print(f"Starting migration of '{queue_name}' to {target_type}...")

    rollback_steps = []
    original_settings = get_queue_settings(vhost, queue_name)
    if not original_settings:
        print(f"Error: Failed to fetch settings for queue '{queue_name}'. Migration aborted.")
        return

    # Check for unsupported features
    if not validate_migration(original_settings, target_type):
        return  # Stop migration if incompatible settings are found

    # Create the target queue
    temp_queue_name = f"{queue_name}_temp_migrated"

    if not create_queue(vhost, temp_queue_name, target_type, original_settings):
        print(f"Error: Failed to create temporary queue '{temp_queue_name}'.")
        return

    rollback_steps.append({"action": "delete_queue", "vhost": vhost, "queue": temp_queue_name})

    # Move messages to temporary queue
    messages = move_messages(vhost, queue_name, temp_queue_name)
    if messages is None:
        print(f"Error: Failed to move messages to temporary queue. Rollback initiated.")
        rollback_migration(rollback_steps)
        return

    # Delete original queue
    if not delete_queue(vhost, queue_name):
        print(f"Error: Failed to delete original queue '{queue_name}'. Rollback initiated.")
        rollback_migration(rollback_steps)
        return

    rollback_steps.append({"action": "create_queue", "vhost": vhost, "queue": queue_name, "data": original_settings})

    # Create the final target queue
    if not create_queue(vhost, queue_name, target_type, original_settings):
        print(f"Error: Failed to recreate queue '{queue_name}' as {target_type}. Rollback initiated.")
        rollback_migration(rollback_steps)
        return

    rollback_steps.append({"action": "delete_queue", "vhost": vhost, "queue": queue_name})

    # Move messages back to new queue
    if not move_messages(vhost, temp_queue_name, queue_name):
        print(f"Error: Failed to move messages back to new queue. Rollback initiated.")
        rollback_migration(rollback_steps)
        return

    # Cleanup temporary queue
    if not delete_queue(vhost, temp_queue_name):
        print(f"Error: Failed to delete temporary queue. Rollback initiated.")
        rollback_migration(rollback_steps)
        return

    print(f"✅ Migration completed! Queue '{queue_name}' is now a {target_type} queue.")

#Moves messages from source_queue to target_queue.
def move_messages(source_vhost, source_queue, target_queue):
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
        print(f"Successfully moved {len(messages)} messages from '{source_queue}' to '{target_queue}'")
        return True
    else:
        print(f"Error fetching messages from '{source_queue}': {response.text if response else 'Unknown error'}")
        return False

#Publishes a message to a queue.
def publish_message(queue_name, message):
    url = f"{RABBITMQ_HOST}/api/exchanges/%2F/amq.default/publish"
    post_body = {
        "properties": message["properties"],
        "routing_key": queue_name,
        "payload": message["payload"],
        "payload_encoding": "string",
    }

    response = _api_request("POST", url, auth=(RABBITMQ_USER, RABBITMQ_PASS), headers=API_HEADERS, json=post_body)
    if not response or response.status_code != 200:
        print(f"Error publishing message to '{queue_name}': {response.text if response else 'Unknown error'}")

#Deletes a queue and returns success status.
def delete_queue(vhost, queue_name):
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"
    response = _api_request("DELETE", url, auth=(RABBITMQ_USER, RABBITMQ_PASS))

    if response and response.status_code in [200, 204]:
        print(f"Queue '{queue_name}' deleted successfully.")
        return True
    else:
        print(f"Error deleting queue '{queue_name}': {response.text if response else 'Unknown error'}")
        return False

#Performs rollback of migration in case of failure.
def rollback_migration(rollback_steps):
    print("Rolling back migration...")

    for step in reversed(rollback_steps):
        action = step["action"]
        vhost = step["vhost"]
        queue_name = step["queue"]

        if action == "delete_queue":
            delete_queue(vhost, queue_name)
        elif action == "create_queue":
            create_queue(vhost, queue_name, "quorum", step.get("data"))

    print("Rollback complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RabbitMQ Queue Migration Tool")
    parser.add_argument("--vhost", required=True, help="Specify the vHost of the queue")
    parser.add_argument("--queue", required=True, help="Specify the name of the queue to migrate")
    parser.add_argument("--type", required=True, choices=["quorum", "stream"], help="Specify the target queue type")

    args = parser.parse_args()
    migrate_queue(args.vhost, args.queue, args.type)
