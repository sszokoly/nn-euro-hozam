
#!/usr/bin/env python3

# Setup logging before importing other modules
from logger_config import setup_logging
from database import Database
setup_logging()

import argparse
import streamlit as st

from loguru import logger
from pathlib import Path


TABLE = "nn_euro_yields"
BASE_DIR = Path.cwd()
DB_DIR = BASE_DIR / "data" / "db"
DB = DB_DIR / f"{TABLE}.db"
XLS_DIR = BASE_DIR / "data" / "xls"
CSV_DIR = BASE_DIR / "data" / "csv"
ST_PAGES_DIR = BASE_DIR / "nn_euro_hozam" / "pages"
ROUND_DIGITS = 4


def main(args=None):
    
    st.set_page_config(layout="wide")
    st.session_state.round_digits = args.round_digits
    
    pages = [
        st.Page(ST_PAGES_DIR / "01_settings.py", title="Settings", icon="⚙️", default=True),
        st.Page(ST_PAGES_DIR / "02_assets.py", title="Assets", icon="💰"),
        st.Page(ST_PAGES_DIR / "03_yields.py", title="Yields V1", icon="📊"),
        st.Page(ST_PAGES_DIR / "04_test.py", title="Yields V2", icon="🚧"),
    ]
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Visualize NN Euro investment asset yield data."
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
