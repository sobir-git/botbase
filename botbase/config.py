import logging
import os
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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
    tracker: str = "jsonl"  # Options: "postgresql" or "jsonl"
    postgres: PostgresConfig = PostgresConfig()
    jsonl: JSONLConfig = JSONLConfig()
    sqlite: SqliteTrackerConfig = SqliteTrackerConfig()
    # List of channel configurations
    channels: List["ChannelConfig"] = Field(default_factory=list)


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
