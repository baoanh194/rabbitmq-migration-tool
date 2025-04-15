# RabbitMQ Migration Tool

The RabbitMQ Migration Toolkit helps users transition their RabbitMQ setups between different queue types and environments.

It provides 4 main functions:
1. Listing Queues:
Detects and displays all queues (with filtering, metrics, and JSON output support) from the RabbitMQ management API.

2. Migration Planning:
Analyzes each queue’s properties (durability, exclusivity, auto-delete, and custom arguments) to determine if it’s fit for migration. It then suggests optimal migration types (Quorum and/or Stream), identifies blockers and warnings, and outputs a detailed migration plan as JSON.

3. Queue creation TODO
4. Rollback TODO

* Note:
The toolkit uses your RabbitMQ credentials configured in config/config.py (make sure to set your RABBITMQ_HOST, RABBITMQ_USER, and RABBITMQ_PASS).

## Installation
### Clone the repository:
```
git clone git@github.com:baoanh194/rabbitmq-migration-tool.git
```

### Install required dependencies:
pip install -r requirements.txt

### Configure RabbitMQ credentials:
Edit the config/config.py file as needed:
```
RABBITMQ_HOST = "http://localhost:15672"
RABBITMQ_USER = "guest"
RABBITMQ_PASS = "guest"
```

## Usage
The toolkit is invoked via the CLI. The main entry point is the cli.py module,
which supports various commands.

### Listing Queues

The `list-queues` command detects and lists all queues in the RabbitMQ cluster,
providing information about their state, policies, and arguments.

```bash
migrationtool list_queues

Queue Name        Messages    State       Policies    Arguments
================================================================================
Test1             0           running     None        {"x-message-ttl": 1000, "x-queue-type": "classic"}
acb               0           running     None        {}
adasdasd          0           running     None        {"x-queue-type": "stream"}
fsdffdsfsdfds     0           running     None        {}
```

Options:

```--name <queue_name>```: Filter queues by name.

```--vhost <vhost_name>```: Filter queues by vhost. Use url encoding for vhost names (e.g., ```%2f``` for ```/```).

```--json```: Output queue details in JSON format.

Example Usage:

Filtering by Queue Name:
```bash
migrationtool list_queues --name acb

Queue Name        Messages    State       Policies    Arguments
================================================================================
acb               0           running     None        {}
```

Filtering by Vhost:
```bash
migrationtool list_queues --vhost %2f

Queue Name        Messages    State       Policies    Arguments
================================================================================
Test1             0           running     None        {"x-message-ttl": 1000, "x-queue-type": "classic"}
acb               0           running     None        {}
adasdasd          0           running     None        {"x-queue-type": "stream"}
fsdffdsfsdfds     0           running     None        {}
```

JSON Output:
```bash
 migrationtool list_queues --name acb --vhost %2f --json

[
  {
    "arguments": {
      "x-message-ttl": 1000,
      "x-queue-type": "classic"
    },
    // ... other queue details ...
    "name": "Test1",
    "vhost": "/"
  },
  {
    "arguments": {},
    // ... other queue details ...
    "name": "acb",
    "vhost": "/"
  },
...
```

Error Handling:
The tool provides improved error handling for invalid filters or missing data.
For example:
```bash
 migrationtool list_queues --vhost /  # Incorrect vhost
❌ Error fetching queue details: 404 Client Error: Not Found for url: http://localhost:15672/api/queues//
```
### Migration Planner
The migration planner analyzes queue properties to determine migration readiness.
It checks for blockers (e.g., non-durable, exclusive, or auto-delete queues)
and warns about unsupported settings.
It then suggests possible migration types (Quorum and/or Stream) and outputs a
detailed plan.

```
migrationtool planner --help
usage: migrationtool planner [-h] [--name NAME] [--vhost VHOST] [--queue QUEUE] [--all] [--json]

options:
  -h, --help     show this help message and exit
  --name NAME    Specify the queue name for migration
  --vhost VHOST  Virtual host (default: %2f)
  --queue QUEUE  Specify a queue name to analyze
  --all          Analyze all queues in the specified vHost
  --json         Output results in JSON format
```

Example (Analyze a specific queue):
```
migrationtool planner --queue acb

**Migration Analysis Result**:
Queue Name: acb
Current Type: quorum

**Good for Migration** → Stream Queue(s)

**Full Migration Plan (JSON Output):**
{
    "queue_name": "acb",
    "vhost": "%2f",
    "current_type": "quorum",
    "suggested_migrations": [
        "stream"
    ],
    "blockers": {
        "quorum": [],
        "stream": []
    },
    "warnings": {
        "quorum": [],
        "stream": []
    },
    "original_settings": {
        "queue_name": "acb",
        "vhost": "%2f",
        "type": "quorum",
        "durable": true,
        "exclusive": false,
        "auto_delete": false,
        "arguments": {
            "leader-locator": "client-local",
            "queue-initial-cluster-size": 3,
            "x-queue-type": "quorum"
        }
    }
}
```

### Queue Creation
Create a new queue based on the migration plan.

Options:
```
rabbitmq-migration create_queue --help
usage: rabbitmq-migration create_queue [-h] --vhost VHOST --queue QUEUE --type {quorum,stream}
  -h, --help            show this help message and exit
  --vhost VHOST         Virtual host for the queue
  --queue QUEUE         Name of the queue to migrate
  --type {quorum,stream}
                        Target queue type
```

```bash
$rabbitmq-migration create_queue --vhost %2f --queue GiaBao --type quorum
✅ Migration completed! Queue 'GiaBao' is now a quorum queue.
```

## Support
For any issues or questions, please open an issue on GitHub or contact the development team.

## Notes and Limitations

- Queues with unsupported features (e.g., x-max-priority, lazy mode, ha-* policies) will be flagged.

- Only queues using supported arguments will be migrated. Others require manual intervention.

- Federation, shovel, and mirror handling are planned in future updates.