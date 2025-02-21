# RabbitMQ Migration Tool

The RabbitMQ Migration Toolkit helps users transition their RabbitMQ setups between different queue types and environments.

## Usage

### Listing Queues

The `list-queues` command detects and lists all queues in the RabbitMQ cluster, providing information about their state, policies, and arguments.

```bash
python3 -m cli.main list-queues

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
python3 -m cli.main --name acb

Queue Name        Messages    State       Policies    Arguments
================================================================================
acb               0           running     None        {}
```

Filtering by Vhost:
```bash
python3 -m cli.main --vhost %2f

Queue Name        Messages    State       Policies    Arguments
================================================================================
Test1             0           running     None        {"x-message-ttl": 1000, "x-queue-type": "classic"}
acb               0           running     None        {}
adasdasd          0           running     None        {"x-queue-type": "stream"}
fsdffdsfsdfds     0           running     None        {}
```

JSON Output:
```bash
python3 -m cli.main --json

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
python3 -m cli.main --vhost /  # Incorrect vhost
❌ Error fetching queue details: 404 Client Error: Not Found for url: http://localhost:15672/api/queues//
```
