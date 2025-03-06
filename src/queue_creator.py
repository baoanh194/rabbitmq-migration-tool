#!/usr/bin/env python3
#=============================================================================
# Copyright (c) 2025, Seventh State
#=============================================================================
# Handles the creation of a new (migrated) queue. It first retrieves the original
# queue’s settings from the RabbitMQ API and then adjusts its configuration to
# meet the requirements of the target queue type (either “quorum” or “stream”).
# It removes settings that aren’t supported by the new type and adds defaults as
# needed. Finally, it makes an API call to create the new queue with the updated
# settings.

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
        print(f"✅ {queue_type.capitalize()} queue '{queue_name}' created successfully.")
    else:
        print(f"❌ Failed to create {queue_type.capitalize()} queue '{queue_name}': {response.text}")

def move_messages(source_vhost, source_queue, target_queue):
    """ Move messages from source_queue to target_queue. """
    url = f"{RABBITMQ_HOST}/api/queues/{source_vhost}/{source_queue}/get"
    headers = {"Content-Type": "application/json"}
    get_body = {
        "count": 1000,  # Fetch 1000 messages at a time
        "requeue": False,
        "encoding": "auto",
        "ackmode": "ack_requeue_false"
    }

    try:
        response = requests.post(url, auth=(RABBITMQ_USER, RABBITMQ_PASS), json=get_body, headers=headers)
        if response.status_code != 200:
            print(f"❌ Error fetching messages from '{source_queue}': {response.text}")
            return

        messages = response.json()
        for message in messages:
            publish_message(target_queue, message)

        print(f"✅ Successfully moved {len(messages)} messages from '{source_queue}' to '{target_queue}'")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error moving messages: {e}")

def publish_message(queue_name, message):
    """ Publish message to a new queue. """
    url = f"{RABBITMQ_HOST}/api/exchanges/%2F/amq.default/publish"
    headers = {"Content-Type": "application/json"}
    post_body = {
        "properties": message["properties"],
        "routing_key": queue_name,
        "payload": message["payload"],
        "payload_encoding": "string"
    }

    try:
        response = requests.post(url, auth=(RABBITMQ_USER, RABBITMQ_PASS), json=post_body, headers=headers)
        if response.status_code != 200:
            print(f"❌ Error publishing message to '{queue_name}': {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error publishing message: {e}")

def delete_queue(vhost, queue_name):
    """ Delete a queue """
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"
    try:
        response = requests.delete(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        if response.status_code in [200, 204]:
            print(f"✅ Queue '{queue_name}' deleted successfully.")
        else:
            print(f"❌ Error deleting queue '{queue_name}': {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error deleting queue: {e}")

def migrate_queue(vhost, queue_name, target_type):
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
