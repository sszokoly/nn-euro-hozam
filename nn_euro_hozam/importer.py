#!/usr/bin/env python3

from fileinput import filename
from multiprocessing.util import debug

import pandas as pd
from loguru import logger
from pathlib import Path
from nn_euro_hozam.xls_to_dict import xls_to_dict
from nn_euro_hozam.db import Database
from datetime import datetime, timedelta


TABLE = "nn_euro_yields"
BASE_DIR = Path.cwd()
DB_DIR = BASE_DIR / "data" / "db"
DB = DB_DIR / f"{TABLE}.db"
XLS_DIR = BASE_DIR / "data" / "xls"
CSV_DIR = BASE_DIR / "data" / "csv"


def coerce_data(data) -> list:
    coerced_data = []
    for record in data:
        coerced_data.append(({
            "asset_name": record["asset_name"],
            "date": record["opening_date"],
            "opening_value": record["opening_value"],
            "closing_value": record["closing_value"],
            "period_yield": record["period_yield"]
        }))
    return coerced_data


def ffill_data(data) -> list:
    ffilled_data = []
    for record in data:
        _, asset_name, opening_date, _, closing_value, _ = record
        opening_dt = datetime.strptime(opening_date, "%Y-%m-%d")
        next_dt = opening_dt + timedelta(days=1)
        next_date = next_dt.strftime("%Y-%m-%d")
        ffilled_data.append(({
            "asset_name": asset_name,
            "date": next_date,
            "opening_value": closing_value,
            "closing_value": closing_value,
            "period_yield": 0
        }))
    return ffilled_data


def import_from_xls(src_dir=XLS_DIR, round_digits=4, db=DB):
    xls_files = sorted(Path(src_dir).rglob("*.xls"))
    database = Database(db=DB, table=TABLE, init_db=True)
    yesterday_date = None
    
    for filepath in xls_files:
        logger.opt(colors=True).debug(f"Loading <yellow>{filepath}</yellow>")
        opening_date, closing_date, data = xls_to_dict(filepath, round_digits)
        if not data and yesterday_date is not None:
            data = database.fetch_by_date(yesterday_date)
            data = ffill_data(data)
        elif opening_date == yesterday_date:
            database.delete_by_date(opening_date)
            continue
        else:
            data = coerce_data(data)
        
        database.insert(data)
        
        if opening_date:
            yesterday_date = opening_date
        elif data:
            yesterday_date = data[0]["date"]
    
    data = database.fetchall()
    df = pd.DataFrame(data, columns=["id", "asset_name", "date",
        "opening_value", "closing_value", "period_yield"])
    df.to_csv(CSV_DIR / "nn_euro_yields.csv", index=False)   
    return df


def import_from_csv():
    csv_file = CSV_DIR / "nn_euro_yields.csv"
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_file}")
        return None
    
    df = pd.read_csv(csv_file)
    return df


if __name__ == '__main__':
    from logger_config import setup_logging
    setup_logging()
    from loguru import logger
    from nn_euro_hozam.db import Database

    database = Database(
        db=Path.cwd() / "data" / "test" /"test.db",
        table="nn_euro_yields",
        init_db=True
    )
    df1 = import_from_xls(src_dir=Path.cwd() / "data" / "xls", db=database)
    df2 = import_from_csv()
    print("==========From XLS=========\n", df1.head(), "\n\n")
    print("==========From CSV=========\n", df2.head(), "\n\n")
