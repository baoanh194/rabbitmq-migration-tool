#=============================================================================
# Copyright (c) 2025, Seventh State
#=============================================================================
# Fetches all queues from the RabbitMQ management API, checks each queue’s
# properties (such as durability, exclusivity, and auto-delete), and reports if
# a queue is fit for migration. It prints a summary table to the console and
# saves the analysis as a JSON report in migration_report.json.

import requests
import json
import argparse
from config.config import RABBITMQ_HOST, RABBITMQ_USER, RABBITMQ_PASS
from src.logger import log_info, log_error
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry))

# Supported settings per queue type
SUPPORTED_SETTINGS = {
    "quorum": {
        "durable": True,
        "supported": [
            "x-expires", "x-max-length", "x-message-ttl", "x-dead-letter-exchange",
            "x-dead-letter-routing-key", "x-max-length-bytes", "delivery-limit",
            "queue-initial-cluster-size", "dead-letter-strategy", "leader-locator"
        ],
        "unsupported": ["exclusive", "auto-delete", "x-max-priority", "x-queue-master-locator", "x-queue-version", "x-queue-mode"]
    },
    "stream": {
        "durable": True,
        "supported": ["x-max-length-bytes", "queue-initial-cluster-size", "leader-locator", "max-time-retention"],
        "unsupported": [
            "exclusive", "auto-delete", "x-max-priority", "x-message-ttl", "x-dead-letter-exchange",
            "x-dead-letter-routing-key", "x-max-length", "x-single-active-consumer", "overflow_behavior",
            "x-queue-master-locator", "x-queue-mode"
        ]
    }
}

UNSUPPORTED_ARGUMENT_VALUES = {
    "x-queue-mode": ["lazy"],
    "overflow": ["reject-publish-dlx"]
}

def get_queue_settings(vhost, queue_name):
    """Fetch queue settings from RabbitMQ API with retries and timeout."""
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}/{queue_name}"

    try:
        response = session.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS), timeout=5)
        response.raise_for_status()
        queue_data = response.json()
        log_info(f"Fetched settings for queue '{queue_name}' in vhost '{vhost}'.")
        return {
            "queue_name": queue_name,
            "vhost": vhost,
            "type": queue_data.get("type", "classic"),
            "durable": queue_data.get("durable", True),
            "exclusive": queue_data.get("exclusive", False),
            "auto_delete": queue_data.get("auto_delete", False),
            "arguments": queue_data.get("arguments", {})
        }

    except requests.exceptions.RequestException as e:
        log_error(f"Error fetching settings for queue '{queue_name}' in vhost '{vhost}': {e}")
        return None

def detect_migration_blockers(queue_info, target_type):
    """Identify migration blockers & warnings based on queue settings."""
    blockers = []
    warnings = []

    settings = SUPPORTED_SETTINGS[target_type]

    if not queue_info["durable"] and settings["durable"]:
        blockers.append("Non-durable queues cannot be migrated.")

    if queue_info["exclusive"]:
        blockers.append("Exclusive queues are not supported.")
    if queue_info["auto_delete"]:
        blockers.append("Auto-delete queues cannot be migrated.")

    arguments = queue_info["arguments"]

    if arguments.get("x-queue-version") == 2 or arguments.get("x-queue-version") == 1:
        warnings.append("Queues with 'x-queue-version' are not supported for Quorum Queues.")

    # Detect unsupported settings
    unsupported_keys = set(arguments.keys()) & set(settings["unsupported"])
    for key in unsupported_keys:
        warnings.append(f"Setting '{key}' will be lost after migration.")

    # Detect unsupported argument values
    for key, bad_values in UNSUPPORTED_ARGUMENT_VALUES.items():
        if key in arguments and arguments[key] in bad_values:
            warnings.append(f"Argument '{key}={arguments[key]}' is not compatible with Quorum Queues.")

    return blockers, warnings

def suggest_migration_types(queue_info):
    """Suggest all possible migration types (Quorum and/or Stream)."""
    if queue_info["type"] in ["quorum", "stream"]:
        return ["stream"] if queue_info["type"] == "quorum" else ["quorum"]

    args = set(queue_info["arguments"].keys())
    quorum_keys = {"x-dead-letter-exchange", "x-message-ttl", "x-max-length"}
    stream_keys = {"x-max-length-bytes", "queue-initial-cluster-size", "leader-locator"}

    possible_migrations = []
    if args & quorum_keys:
        possible_migrations.append("quorum")
    if args & stream_keys:
        possible_migrations.append("stream")

    return possible_migrations or ["quorum", "stream"]

def generate_migration_plan(vhost, queue_name):
    """Generate a migration plan for a queue."""
    queue_info = get_queue_settings(vhost, queue_name)
    if not queue_info:
        log_error(f"Failed to generate migration plan for queue '{queue_name}' in vhost '{vhost}'.")
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
    log_info(f"Generated migration plan for queue '{queue_name}': {json.dumps(migration_plan)}")
    return migration_plan

def get_all_queues(vhost):
    url = f"{RABBITMQ_HOST}/api/queues/{vhost}"

    try:
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error fetching queues: {e}")
        return []

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
    parser = argparse.ArgumentParser(description="Analyze RabbitMQ queues for migration.")
    parser.add_argument("--vhost", default="%2f", help="Virtual host (default: %(default)s)")
    parser.add_argument("--queue", help="Specific queue to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all queues in the vHost")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    vhost = args.vhost
    queue_name = args.queue
    process_all = args.all

    if process_all:
        results = analyze_all_queues(vhost)
        if args.json:
            print(json.dumps(results, indent=4))
        else:
            with open("migration_report.json", "w") as f:
                json.dump(results, f, indent=4)
            log_info(f"Saved migration report for all queues in vhost '{vhost}'.")
            print(f"\nMigration report saved: migration_report.json")
    elif queue_name:
        migration_plan = generate_migration_plan(vhost, queue_name)
        if not migration_plan:
            print("Failed to generate migration plan.")
            return
        if args.json:
            print(json.dumps(migration_plan, indent=4))
        else:
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
                    print(f"\n**Warnings for {migration_type.capitalize()} Migration**:")
                    for warning in warnings:
                        print(f"   - {warning}")

            print("\n**Full Migration Plan (JSON Output):")
            print(json.dumps(migration_plan, indent=4))
    else:
        print("Please provide --queue or --all argument")


if __name__ == "__main__":
    main()
