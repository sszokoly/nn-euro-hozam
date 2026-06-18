#!/usr/bin/env python3

import sys
import yaml
from pathlib import Path
from loguru import logger


ROUND_DIGITS = 4

BASE_DIR = Path(__file__).resolve().parent
DB_DIR =  BASE_DIR / "data" / "db"
CSV_DIR = BASE_DIR / "data" / "csv"
XLS_DIR = BASE_DIR / "data" / "xls"
TMP_DIR = BASE_DIR / "data" / "tmp"

LOGGER_CONFIG_FILE_NAME = "logger_config.yaml"
LOGGER_CONFIG_FILE_PATH = BASE_DIR / LOGGER_CONFIG_FILE_NAME

BASE_FILE_NAME = "nn_euro_saving_app"
DB_FILE = DB_DIR / f"{BASE_FILE_NAME}.db"
DB_FILE_BKP = f"{DB_FILE}.bkp.db"
CSV_FILE = CSV_DIR / f"{BASE_FILE_NAME}.csv"
DB_NN_TABLE_NAME = "nn_euro_saving"
DB_ST_TABLE_NAME = "streamlit"


NN_TABLE_SCHEMA = [
    ("id", "INTEGER", "PRIMARY KEY"),
    ("asset", "TEXT", "NOT NULL"),
    ("opening_date", "TEXT", "NOT NULL"),
    ("opening_euro_value", "REAL", ""),
    ("closing_date", "TEXT", "NOT NULL"),
    ("closing_euro_value", "REAL", ""),
    ("yield_ratio", "REAL", ""),
]

ST_TABLE_SCHEMA = [
    ("id", "INTEGER", "PRIMARY KEY"),
    ("key", "TEXT", "NOT NULL"),
    ("value", "TEXT", "NOT NULL"),
]

FIELD_NAMES = tuple(col[0] for col in NN_TABLE_SCHEMA)

HEADER_MAP = {
    "Eszközalap": FIELD_NAMES[1],
    "Eszközalap neve": FIELD_NAMES[1],
    "Kezdő dátum": FIELD_NAMES[2],
    "Kezdő árfolyam": FIELD_NAMES[3],
    "Záró dátum": FIELD_NAMES[4],
    "Záró árfolyam": FIELD_NAMES[5],
    "Hozam": FIELD_NAMES[6],
}

COLORS = {
    'Aktív hozamfigyelõ vegyes eszközalap - D': '#1F77B4',  # Strong Blue
    'Euró likviditás eszközalap - D': '#FF7F0E',            # Vivid Orange
    'Európai ingatlancégek részv. eszközalap': '#2CA02C',   # Clear Green
    'Európai kötvény eszközalap - D': '#D62728',            # Bold Red
    'Európai részvény eszközalap': '#9467BD',               # Distinct Purple
    'Európai vállalati kötvény eszközalap': '#8C564B',      # Earthy Brown
    'Fejlõdõ piaci részvény ESG eszközalap-D': '#E377C2',   # Bright Pink
    'Fejlõdõ ázsiai részvény eszközalap': '#7F7F7F',        # Neutral Grey
    'Fenntartható növekedés részvény eszk.': '#BCBD22',     # Olive Yellow
    'Globális egészségügyi részvény eszk.': '#17BECF',      # Cyan/Teal
    'Globális növekedési részvény eszközalap': '#AEC7E8',   # Light Blue
    'Kiegyensúlyozott vegyes eszközalap - D': '#FFBB78',    # Light Orange
    'Latin-amerikai részvény eszközalap': '#98DF8A',        # Light Green
    'Magas kötvény arányú vegyes eszk. - D': '#FF9896',     # Light Red
    'Magas védelmû vegyes eszközalap': '#C5B0D5',           # Light Purple
    'Nemz. élelmiszeripari cégek rv. ea - D': '#C49C94',    # Light Brown
    'Nyersanyagpiaci részvény eszközalap': '#F7B6D2',       # Light Pink
    'Presztízs- és luxusmárkák rv. ea.': '#C7C7C7',         # Light Grey
    'USA részvény eszközalap': '#DBDB8D',                   # Light Yellow
    'Ázsia kötvény eszközalap': '#9EDAE5'                   # Light Cyan
}


def setup_logging():
    with open(LOGGER_CONFIG_FILE_PATH) as fd:
        config = yaml.safe_load(fd)

    # Manually resolve sinks
    for handler in config.get("handlers", []):
        if handler.get("sink") == "ext://sys.stderr":
            handler["sink"] = sys.stderr
        elif handler.get("sink") == "ext://sys.stdout":
            handler["sink"] = sys.stdout

    logger.configure(**config)


if __name__ == "__main__":
    from config import *
    setup_logging()
    print(f"DB_FILE: {DB_FILE}")
    logger.info("Logging is configured and ready to use.")
