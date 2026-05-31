#!/usr/bin/env python3

import sys
import yaml
from loguru import logger
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE_NAME = "logger_config.yaml"
CONFIG_FILE_PATH = BASE_DIR / CONFIG_FILE_NAME


def setup_logging():
    with open(CONFIG_FILE_PATH, "r") as f:
        config = yaml.safe_load(f)

    # Manually resolve sinks
    for handler in config.get("handlers", []):
        if handler.get("sink") == "ext://sys.stderr":
            handler["sink"] = sys.stderr
        elif handler.get("sink") == "ext://sys.stdout":
            handler["sink"] = sys.stdout

    logger.configure(**config)


if __name__ == "__main__":
    setup_logging()
    logger.info("Logging is configured and ready to use.")
