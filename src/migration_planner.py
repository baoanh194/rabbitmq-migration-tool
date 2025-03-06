#=============================================================================
# Copyright (c) 2025, Seventh State
#=============================================================================
# Fetches all queues from the RabbitMQ management API, checks each queue’s
# properties (such as durability, exclusivity, and auto-delete), and reports if
# a queue is fit for migration. It prints a summary table to the console and
# saves the analysis as a JSON report in migration_report.json.

import requests
import json
from config.config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS

# Supported settings per queue type
SUPPORTED_SETTINGS = {
    "quorum": {
        "durable": True,
        "supported": [
            "x-expires", "x-max-length", "x-message-ttl", "x-dead-letter-exchange",
            "x-dead-letter-routing-key", "x-max-length-bytes", "delivery-limit",
            "queue-initial-cluster-size", "dead-letter-strategy", "leader-locator"
        ],
        "unsupported": ["exclusive", "auto-delete", "x-max-priority", "master-locator", "version"]
    },
    "stream": {
        "durable": True,
        "supported": ["x-max-length-bytes", "queue-initial-cluster-size", "leader-locator", "max-time-retention"],
        "unsupported": [
            "exclusive", "auto-delete", "x-max-priority", "x-message-ttl", "x-dead-letter-exchange",
            "x-dead-letter-routing-key", "x-max-length", "x-single-active-consumer", "overflow_behavior"
        ]
    }
}

def get_queue_settings(vhost, queue_name):
    """Fetch queue settings from RabbitMQ API."""
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"

    try:
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()
        queue_data = response.json()

        return {
            "queue_name": queue_name,
            "vhost": vhost,
            "type": queue_data.get("type", "classic"),  # Can be "classic", "quorum", or "stream"
            "durable": queue_data.get("durable", True),
            "exclusive": queue_data.get("exclusive", False),
            "auto_delete": queue_data.get("auto_delete", False),
            "arguments": queue_data.get("arguments", {})
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching queue settings: {e}")
        return None

def detect_migration_blockers(queue_info, target_type):
    """Identify migration blockers & warnings based on queue settings."""
    blockers = []
    warnings = []

    settings = SUPPORTED_SETTINGS[target_type]

    # Check durability
    if not queue_info["durable"] and settings["durable"]:
        blockers.append("Non-durable queues cannot be migrated to quorum or stream.")

    # Check if queue is exclusive or auto-delete
    if queue_info["exclusive"]:
        blockers.append("Exclusive queues are not supported in quorum or stream.")
    if queue_info["auto_delete"]:
        blockers.append("Auto-delete queues cannot be migrated to quorum or stream.")

    # Compare arguments
    for key in queue_info["arguments"]:
        if key in settings["unsupported"]:
            warnings.append(f"Setting '{key}' will be lost after migration.")

    return blockers, warnings

def suggest_migration_types(queue_info):
    """Suggest all possible migration types (Quorum and/or Stream)."""
    if queue_info["type"] in ["quorum", "stream"]:
        return ["stream"] if queue_info["type"] == "quorum" else ["quorum"]

    args = queue_info["arguments"]
    possible_migrations = []

    if any(key in args for key in ["x-dead-letter-exchange", "x-message-ttl", "x-max-length"]):
        possible_migrations.append("quorum")

    if any(key in args for key in ["x-max-length-bytes", "queue-initial-cluster-size", "leader-locator"]):
        possible_migrations.append("stream")

    if not possible_migrations:
        possible_migrations = ["quorum", "stream"]

    return possible_migrations

def generate_migration_plan(vhost, queue_name):
    """Generate a migration plan for a queue."""
    queue_info = get_queue_settings(vhost, queue_name)
    if not queue_info:
        return None

    suggested_types = suggest_migration_types(queue_info)
    blockers_quorum, warnings_quorum = detect_migration_blockers(queue_info, "quorum")
    blockers_stream, warnings_stream = detect_migration_blockers(queue_info, "stream")

    migration_plan = {
        "queue_name": queue_name,
        "vhost": vhost,
        "current_type": queue_info["type"],
        "suggested_migrations": suggested_types,
        "blockers": {
            "quorum": blockers_quorum,
            "stream": blockers_stream
        },
        "warnings": {
            "quorum": warnings_quorum,
            "stream": warnings_stream
        },
        "original_settings": queue_info
    }

    return migration_plan

# Fetch all queues from RabbitMQ API for a given vHost
def get_all_queues(vhost):
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}"

    try:
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error fetching queues: {e}")
        return []

# Analyze all queues in a vHost and generate a full migration report.
def analyze_all_queues(vhost):
    queues = get_all_queues(vhost)
    migration_results = []

    for queue in queues:
        queue_name = queue["name"]
        print(f"Analyzing queue: {queue_name}...")

        migration_plan = generate_migration_plan(vhost, queue_name)
        if migration_plan:
            migration_results.append(migration_plan)

    return migration_results

def main():
    vhost = input("Enter vHost (default: '%2f'): ") or "%2f"
    process_all = input("Analyze all queues? (y/N): ").strip().lower() == 'y'

    if process_all:
        results = analyze_all_queues(vhost)
        with open("migration_report.json", "w") as f:
            json.dump(results, f, indent=4)

        print(f"\n✅ Migration report saved: migration_report.json")
    else:
        queue_name = input("Enter queue name: ")
        migration_plan = generate_migration_plan(vhost, queue_name)
        if not migration_plan:
            print("Failed to generate migration plan.")
            return

        print("\n**Migration Analysis Result**:")
        print(f"Queue Name: {migration_plan['queue_name']}")
        print(f"Current Type: {migration_plan['current_type']}")

        has_blockers = any(migration_plan["blockers"][mt] for mt in migration_plan["blockers"])

        if not has_blockers:
            good_migrations = [mt.capitalize() for mt in migration_plan["suggested_migrations"]]
            if good_migrations:
                print(f"\n**Good for Migration** → {', '.join(good_migrations)} Queue(s)")

        if has_blockers:
            print("\n**Bad for Migration** (Blockers detected):")
            for migration_type, reasons in migration_plan["blockers"].items():
                if reasons:
                    print(f"   - {migration_type.capitalize()}: {', '.join(reasons)}")

        for migration_type, warnings in migration_plan["warnings"].items():
            if warnings:
                print(f"\n⚠️ **Warnings for {migration_type.capitalize()} Migration**:")
                for warning in warnings:
                    print(f"   - {warning}")

        print("\n**Full Migration Plan (JSON Output):**")
        print(json.dumps(migration_plan, indent=4))


if __name__ == "__main__":
    main()