#=============================================================================
# Copyright (c) 2025, Seventh State
#=============================================================================
# Fetches all queues from the RabbitMQ management API, checks each queue’s
# properties (such as durability, exclusivity, and auto-delete), and reports if
# a queue is fit for migration. It prints a summary table to the console and
# saves the analysis as a JSON report in migration_report.json.

import requests
import json
import os

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "http://localhost:15672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

def analyze_queue(queue):
    name = queue.get("name", "N/A")
    durable = queue.get("durable", False)
    exclusive = queue.get("exclusive", False)
    auto_delete = queue.get("auto_delete", False)
    # arguments = queue.get("arguments", {})

    migration_issues = []

    if not durable:
        migration_issues.append("Queue is not durable (QQ/Streams require durable queues).")

    if exclusive:
        migration_issues.append("Exclusive queues cannot be migrated.")

    if auto_delete:
        migration_issues.append("Auto-delete queues are not supported in QQ/Streams.")

    # if "x-message-ttl" in arguments:
    #     migration_issues.append("Message TTL requires review before migration.")

    # if "x-dead-letter-exchange" in arguments:
    #     migration_issues.append("Check dead-letter exchange bindings.")

    return {
        "name": name,
        "migration_possible": len(migration_issues) == 0,
        "issues": migration_issues
    }

def analyze_migration():
    url = f"{RABBITMQ_HOST}/api/queues"

    try:
        response = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASS))
        response.raise_for_status()
        queues = response.json()

        if not queues:
            print("🔹 No queues found.")
            return

        results = [analyze_queue(q) for q in queues]

        print(f"\n{'Queue Name':<20}{'Migration Feasible':<20}{'Issues'}")
        print("=" * 80)

        for result in results:
            name = result["name"]
            feasible = "✅ Yes" if result["migration_possible"] else "❌ No"
            issues = "; ".join(result["issues"]) if result["issues"] else "None"
            print(f"{name:<20}{feasible:<20}{issues}")

        # Output as JSON (optional)
        with open("migration_report.json", "w") as f:
            json.dump(results, f, indent=2)

        print("\n📄 Migration feasibility report saved to `migration_report.json`.")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching queue details: {e}")

if __name__ == "__main__":
    analyze_migration()