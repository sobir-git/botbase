import logging
import os
import re
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Regular expression to match ${VAR_NAME} patterns
env_var_pattern = re.compile(r"\$\{([^}^{]+)\}")


def env_var_constructor(loader, node):
    """
    Extracts the environment variable from the node's value.
    """
    value = loader.construct_scalar(node)
    match = env_var_pattern.findall(value)  # Find all env variables in the value
    if match:
        full_value = value
        for g in match:
            full_value = full_value.replace(f"${{{g}}}", os.environ.get(g, g))
        return full_value
    return value


yaml.SafeLoader.add_implicit_resolver("!env_var", env_var_pattern, None)
yaml.SafeLoader.add_constructor("!env_var", env_var_constructor)


class PostgresConfig(BaseModel):
    url: str = "postgresql+asyncpg://user:password@localhost/dbname"


class JSONLConfig(BaseModel):
    file_path: str = "./conversation_events.jsonl"


class SqliteTrackerConfig(BaseModel):
    db_path: str = "./conversation_events.db"


# Use a dynamic model that allows arbitrary extra fields.
class ChannelConfig(BaseModel):
    type: str
    name: str
    # All other fields will be treated as arguments
    arguments: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        # Extract name and treat all other fields as arguments
        name = data.pop("name", None)
        type = data.pop("type", None)
        if name is None and type is None:
            raise ValueError("At least one of 'name' and 'type' is required.")

        if name is None or type is None:
            name = name or type
            type = type or name

        arguments = data  # remaining fields become arguments
        super().__init__(type=type, name=name, arguments=arguments)


class AppConfig(BaseModel):
    tracker: str = "jsonl"  # Options: "postgresql", "jsonl", or "sqlite"
    postgres: PostgresConfig = PostgresConfig()
    jsonl: JSONLConfig = JSONLConfig()
    sqlite: SqliteTrackerConfig = SqliteTrackerConfig()
    channels: List[ChannelConfig] = Field(default_factory=list)


# Allow self-referencing models.
AppConfig.model_rebuild()


def load_config():
    config_file = os.getenv("CONFIG_FILE", "config.yml")
    if os.path.exists(config_file):
        logger.info(f"Loading configuration from {config_file}")
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}
        return AppConfig(**data)
    logger.warning(f"Config file {config_file} not found. Using default configuration.")
    return AppConfig()


config = load_config()
