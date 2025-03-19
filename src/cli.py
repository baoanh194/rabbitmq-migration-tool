#!/usr/bin/env python3
#=============================================================================
# Copyright (c) 2025, Seventh State
#=============================================================================
# CLI tool for managing RabbitMQ queues.

import requests
import json
import argparse
from config.config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS
import subprocess

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

            print(f"{vhost:<20}{name:<20}{messages:<10}{state:<15}{policies:<10}{publish_rate:<15.2f}{deliver_rate:<15.2f} {json.dumps(arguments)}")


    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching queue details: {e}")

def run_migration_planner(args):
    """Runs migration_planner.py as a subprocess."""
    command = ["python3", "src/migration_planner.py"]
    if args.vhost:
        command.extend(["--vhost", args.vhost])
    if args.queue:
        command.extend(["--queue", args.queue])
    if args.all:
        command.append("--all")
    if args.json:
        command.append("--json")

    subprocess.run(command)

def run_queue_creator(args):
    command = ["python3", "src/queue_creator.py", "--vhost", args.vhost, "--queue", args.queue, "--type", args.type]
    subprocess.run(command)

def main():
    parser = argparse.ArgumentParser(description="CLI for various RabbitMQ migration tasks")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    ## lists queues comamnds
    list_parser = subparsers.add_parser("list_queues", help="List RabbitMQ queues")
    list_parser.add_argument("--name", help="Filter queues by name")
    list_parser.add_argument("--vhost", help="Filter queues by vhost")
    list_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    list_parser.set_defaults(func=lambda args: list_queues(queue_name=args.name, vhost=args.vhost, json_output=args.json))

    ## planner commands
    planner_parser = subparsers.add_parser("planner", help="Analyze queue migration suitability")
    planner_parser.add_argument("--name", help="Specify the queue name for migration")
    planner_parser.add_argument("--vhost", default="%2f", help="Virtual host (default: %(default)s)")
    planner_parser.add_argument("--queue", help="Specify a queue name to analyze")
    planner_parser.add_argument("--all", action="store_true", help="Analyze all queues in the specified vHost")
    planner_parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    planner_parser.set_defaults(func=lambda args: run_migration_planner(args))

    ## creator commands
    creator_parser = subparsers.add_parser("create_queue", help="Migrate (create) a new queue using queue_creator module")
    creator_parser.add_argument("--vhost", required=True, help="Virtual host for the queue")
    creator_parser.add_argument("--queue", required=True, help="Name of the queue to migrate")
    creator_parser.add_argument("--type", required=True, choices=["quorum", "stream"], help="Target queue type")
    creator_parser.set_defaults(func=lambda args: run_queue_creator(args))

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
