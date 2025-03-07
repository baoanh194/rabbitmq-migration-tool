#!/usr/bin/env python3
#=============================================================================
# Copyright (c) 2025, Seventh State
#=============================================================================
# CLI tool for managing RabbitMQ queues.

import requests
import json
import argparse
from config.config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS

def list_queues(queue_name=None, vhost=None, json_output=False):
    url = f"{RABBITMQ_HOST}/api/queues"
    if vhost:
        url = f"{RABBITMQ_HOST}/api/queues/{vhost}"

    try:
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()

        queues = response.json()
        if not queues:
            print("No queues found.")
            return

        if queue_name:
            queues = [q for q in queues if queue_name in q.get("name", "")]

        if json_output:
            print(json.dumps(queues, indent=2))
            return

        print(f"{'VHost':<20}{'Queue Name':<20}{'Messages':<10}{'State':<15}{'Policies':<10}{'Publish/s':<15}{'Deliver/s':<15}{'Arguments':<10}")
        print("=" * 120)

        for queue in queues:
            name = queue.get("name", "N/A")
            vhost = queue.get("vhost", "N/A")
            messages = queue.get("messages", 0)
            state = queue.get("state", "unknown")
            policies = queue.get("policy", "None")
            arguments = queue.get("arguments", {})

            message_stats = queue.get("message_stats", {})
            publish_rate = message_stats.get("publish_details", {}).get("rate", 0.0)
            deliver_rate = message_stats.get("deliver_details", {}).get("rate", 0.0)

            print(f"{vhost:<20}{name:<20}{messages:<10}{state:<15}{policies:<10}{publish_rate:<15.2f}{deliver_rate:<15.2f}{json.dumps(arguments):<10}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching queue details: {e}")

def main():
    parser = argparse.ArgumentParser(prog="migrationtool", description="Migration Tool CLI for RabbitMQ")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list_queues", help="List RabbitMQ queues")
    list_parser.add_argument("--name", help="Filter queues by name")
    list_parser.add_argument("--vhost", help="Filter queues by vhost")
    list_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    list_parser.set_defaults(func=lambda args: list_queues(queue_name=args.name, vhost=args.vhost, json_output=args.json))

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
