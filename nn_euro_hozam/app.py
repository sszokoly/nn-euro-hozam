
#!/usr/bin/env python3

# Setup logging before importing other modules
from logger_config import setup_logging
setup_logging()

import argparse
import pandas as pd
import sys
from db import Database
from loguru import logger
from data_processor import get_df_from_db
from pathlib import Path

import streamlit as st


TABLE = "nn_euro_yields"
BASE_DIR = Path.cwd()
DB_DIR = BASE_DIR / "data" / "db"
DB = DB_DIR / f"{TABLE}.db"
XLS_DIR = BASE_DIR / "data" / "xls"
CSV_DIR = BASE_DIR / "data" / "csv"
ST_PAGES_DIR = BASE_DIR / "nn_euro_hozam" / "pages"


def main(args=None):
    logger.info("Starting the application...")
    try:
        if args is None:
            logger.warning("No arguments provided, using default values.")
            args = argparse.Namespace(
                db=DB,
                table=TABLE,
                src_dir=XLS_DIR,
                round_digits=4,
                init_db=True
            )

        df = get_df_from_db(
            db=args.db,
            table=args.table,
            src_dir=args.src_dir,
            round_digits=args.round_digits,
            init_db=args.init_db,
        )
        if args.init_db:
            df.to_csv(CSV_DIR / "nn_euro_yields.csv", index=True)
        
        
        # Initialize the DataFrame in session state once
        if "df" not in st.session_state:
            st.session_state.df = df
        
        st.set_page_config(layout="wide")
        pg = st.navigation([
            st.Page(ST_PAGES_DIR / "01_setup.py", title="Setup", icon="⚙️"),
            st.Page(ST_PAGES_DIR / "02_visualize.py", title="Data Visualization", icon="📊"),
        ])
        pg.run()
        
    except Exception as e:
        logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Visualize NN Euro investment asset yield data."
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        default=True,
        required=False,
        help="Initialize database and process all data.",
    )
    parser.add_argument(
        "--db",
        required=False,
        type=Path,
        default=DB,
        help=f"DB file path, defaults to {DB}",
    )
    parser.add_argument(
        "--table",
        type=str,
        default=None,
        required=False,
        help=f"DB TABLE name, defaults to {TABLE}",
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=XLS_DIR,
        required=False,
        help=f"Folder containing the yield spreadsheets. Defaults to {XLS_DIR}.",
    )
    parser.add_argument(
        "--round-digits",
        type=int,
        default=4,
        required=False,
        help="Optionally round parsed float values to this many decimal places.",
    )
    args = parser.parse_args()
    main(args=args)
