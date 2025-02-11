import click
from migrations.list_queues import list_queues

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@click.group()
def cli():
    """RabbitMQ Migration Toolkit"""
    pass

@cli.command()
def list_queues_cmd():
    """List all queues in RabbitMQ"""
    list_queues()

if __name__ == "__main__":
    cli()
