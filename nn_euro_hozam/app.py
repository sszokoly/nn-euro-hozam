#!/usr/bin/env python3

from logger_config import setup_logging
setup_logging()
from loguru import logger

import argparse
import streamlit as st
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
    
    # Inject Custom CSS with robust selectors for Streamlit >= 1.40
    st.markdown("""
        <style>
        /* Target the navigation links directly */
        div[data-testid="stSidebarNav"] li a {
            font-size: 18px !important; 
            font-weight: bold !important;
            padding-top: 5px !important;
            padding-bottom: 5px !important;
        }

        /* Target the icon span inside the link */
        div[data-testid="stSidebarNav"] li a span {
            font-size: 18px !important;
            margin-right: 5px;
        }
        
        /* Ensure the list items have enough height */
        div[data-testid="stSidebarNav"] ul li {
            min-height: 35px;
        }
        </style>
    """, unsafe_allow_html=True)

    
    if args:
        st.session_state.round_digits = args.round_digits
    
    pages = [
        st.Page(ST_PAGES_DIR / "01_settings.py",
            title="Settings",
            icon="⚙️", 
            default=True
        ),
        st.Page(ST_PAGES_DIR / "02_downloader.py",
            title="Downloader",
            icon="📥"
        ),
        st.Page(ST_PAGES_DIR / "03_dataframe.py",
            title="Dataframe",
            icon="📋"
        ),
        st.Page(ST_PAGES_DIR / "04_yields.py",
            title="Yields",
            icon="💰"
        ),
        st.Page(ST_PAGES_DIR / "05_values.py",
            title="Values",
            icon="📈"
        ),
    ]
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Visualize NN Euro investment data."
    )
    parser.add_argument(
        "--round-digits",
        type=int,
        default=4,
        required=False,
        help="Round float to this many decimal places.",
    )
    args = parser.parse_args()
    main(args=args)
