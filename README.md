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
fsdffdsfsdfds    0           running     None        {}
