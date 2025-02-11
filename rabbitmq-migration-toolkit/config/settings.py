import yaml  # Importing PyYAML to parse YAML configuration files

def load_config():
    """Load RabbitMQ settings from config.yaml."""
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)
