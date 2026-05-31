
#!/usr/bin/env python3

# Setup logging before importing other modules
from logger_config import setup_logging
setup_logging()

import argparse
import pandas as pd
import streamlit as st
import sys
from db import Database
from loguru import logger
from data_processor import xls_to_db_data
from df_processor import db_to_df_data
from pathlib import Path


TABLE = "nn_euro_yields"
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "db"
DB = DB_DIR /  f"{TABLE}.db"
DF_DIR = BASE_DIR / "csv"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualize NN Euro investment asset yield data."
    )
    parser.add_argument(
        "--init",
        action="store_true",
        default=True,
        required=False,
        help="Drop and recreate the database table.",
    )
    parser.add_argument(
        "--db",
        required=False,
        type=str,
        default=None,
        help="Database file path",
    )
    parser.add_argument(
        "--table",
        type=str,
        default=None,
        required=False,
        help="Database table name",

    )
    parser.add_argument(
        "--src-dir",
        type=str,
        default="data",
        required=False,
        help="Folder containing the source yield spreadsheets. Defaults to 'data'.",
    )
    parser.add_argument(
        "--round-digits",
        type=int,
        default=4,
        required=False,
        help="Optionally round parsed float values to this many decimal places.",
    )
    return parser.parse_args()


def main():
    logger.info("Starting the application...")
    try:
        args = _parse_args()
        
        # Initialize database
        db = Database(db=args.db, table=args.table)
        if args.init:
            db.drop()
            db.create()
        
        # Insert processed data into the database
        db_in_data = xls_to_db_data(src_dir=args.src_dir, round_digits=args.round_digits)
        db.insert(db_in_data)
        
        # Fetch all DB data and convert to DataFrame for visualization
        df = db_to_df_data(db.fetchall())
        df.to_csv(DF_DIR / "nn_euro_yields.csv", index=False)
        
        logger.info("Application finished successfully.")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    import sys
    sys.argv.extend([
        "--init",
    ])
    main()