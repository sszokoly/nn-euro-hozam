#!/usr/bin/env python3

import pandas as pd
from datetime import datetime, timedelta
from fileinput import filename
from loguru import logger
from multiprocessing.util import debug
from pathlib import Path
from xls_to_dict import xls_to_dict

from database import Database
from config import (
    DB_FILE,
    XLS_DIR,
    CSV_FILE,
    FIELD_NAMES,
    ROUND_DIGITS
)


def value_ma_90d(df):
    # Calculate a 90-day rolling average (approx. 3 months)
    # min_periods=1 ensures you get a value even at the start
    df["value_ma_90d"] = (
        df.groupby("asset")["opening_euro_value"]
        .rolling(window=90, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True) # Align index back to original
    )
    return df


def period_yield_pct_cumprod(df, round_digit=ROUND_DIGITS):
    df["growth_factor"] = 1 + df["period_yield_pct"]
    df["cumulative_growth"] = (
        df.groupby("asset")["growth_factor"]
          .cumprod()
          .round(decimals=round_digit)
    )
    df["period_yield_pct_cumprod"] = (
        (df["cumulative_growth"] - 1) * 100).round(decimals=round_digit)
    return df


def coerce_data(data) -> list:
    coerced_data = []
    for record in data:
        coerced_data.append(({
            "asset": record["asset"],
            "opening_date": record["opening_date"].isoformat(),
            "opening_euro_value": record["opening_euro_value"],
            "closing_date": record["closing_date"].isoformat(),
            "closing_euro_value": record["closing_euro_value"],
            "period_yield_pct": record["period_yield_pct"]
        }))
    return coerced_data


def ffill_data(data) -> list:
    ffilled_data = []
    for record in data:
        _, asset, opening_date, _, _, closing_euro_value, _ = record
        opening_dt = datetime.strptime(opening_date, "%Y-%m-%d").date()
        next_dt = opening_dt + timedelta(days=1)
        ffilled_data.append(({
            "asset": asset,
            "opening_date": next_dt.strftime("%Y-%m-%d"),
            "opening_euro_value": closing_euro_value,
            "closing_date": next_dt.strftime("%Y-%m-%d"),
            "closing_euro_value": closing_euro_value,
            "period_yield_pct": 0.0
        }))
    return ffilled_data


def data_to_dataframe(data):
    df = pd.DataFrame(data, columns=FIELD_NAMES)
    df = value_ma_90d(df)
    df = period_yield_pct_cumprod(df)
    return df


def import_nn_from_xls(
    src_dir=XLS_DIR,
    round_digits=ROUND_DIGITS,
    db_file=DB_FILE,
    csv_file=CSV_FILE,
):
    xls_files = sorted(Path(src_dir).rglob("*.xls"))
    database = Database(db_file=db_file)
    database.deleteall(table_name="nn")
    yesterday_date = None
    
    for filepath in xls_files:
        logger.opt(colors=True).debug(f"Loading <yellow>{filepath}</yellow>")
        opening_date, closing_date, data = xls_to_dict(filepath, round_digits)
        
        if not opening_date and not closing_date:
            if yesterday_date:
                data = database.fetch_by_date(yesterday_date.isoformat())
                data = ffill_data(data)
                database.insert(data)
                yesterday_date += timedelta(days=1)
            else:
                # nothing to do, just continue
                continue
        
        elif opening_date and closing_date:
            while yesterday_date and yesterday_date < opening_date - timedelta(days=1):
                data2 = database.fetch_by_date(yesterday_date.isoformat())
                data2 = ffill_data(data2)
                database.insert(data2)
                yesterday_date += timedelta(days=1)
        
            if opening_date == yesterday_date:
                database.delete_by_date(opening_date.isoformat())
        
            data = coerce_data(data)
            database.insert(data)
            yesterday_date = opening_date

    data = database.fetchall()
    df = data_to_dataframe(data)
    df.to_csv(csv_file, index=False)
    return df


def import_nn_from_csv(csv_file=CSV_FILE):
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_file}")
        return None
    df = pd.read_csv(csv_file)
    return df


def load_nn_from_db(db_file=DB_FILE):
    database = Database(db_file=db_file)
    data = database.fetchall()
    df = data_to_dataframe(data)
    return df


def merge_xls_with_nn(
    files,
    round_digits=ROUND_DIGITS,
    db_file=DB_FILE,
    csv_file=CSV_FILE,
):
    if not files:
        return
    
    database = Database(db_file=db_file)
    last = database.fetch_last()
    yesterday_date = datetime.strptime(last[0][2], "%Y-%m-%d").date()
    
    for file in files:
        
        filepath = Path(file).resolve()
        if not filepath.exists():
            continue
        
        logger.opt(colors=True).info(f"Loading <yellow>{filepath}</yellow>")
        opening_date, closing_date, data = xls_to_dict(filepath, round_digits)

        if not opening_date and not closing_date:
            if yesterday_date:
                data = database.fetch_by_date(yesterday_date.isoformat())
                data = ffill_data(data)
                database.insert(data)
                yesterday_date += timedelta(days=1)
            else:
                # nothing to do, just continue
                continue

        elif opening_date and closing_date:
            while yesterday_date and yesterday_date < opening_date - timedelta(days=1):
                data2 = database.fetch_by_date(yesterday_date.isoformat())
                data2 = ffill_data(data2)
                database.insert(data2)
                yesterday_date += timedelta(days=1)
        
            if opening_date == yesterday_date:
                database.delete_by_date(opening_date.isoformat())
        
            data = coerce_data(data)
            database.insert(data)
            yesterday_date = opening_date

    data = database.fetchall()
    df = data_to_dataframe(data)
    df.to_csv(csv_file, index=False)
    return df


if __name__ == '__main__':
    from logger_config import setup_logging
    setup_logging()
    from loguru import logger
    from database import Database

    df = merge_xls_with_nn(["data/xls/NN_eszkozalap_hozamok_2026-06-07_2026-06-08.xls"])
    # df = import_nn_from_xls(src_dir=XLS_DIR, db_file=DB_FILE)
    # print(f"==========From XLS=========\nShape: {df.shape}\n", df.head(), "\n\n")
    # chart_df = df.loc[
    #     (df['opening_date'] >= '2025-12-30') &
    #     (df['opening_date'] <= '2026-01-10')
    # ]
    # print(f"==========FILTERED=========\nShape: {chart_df.shape}\n", chart_df.head(), "\n\n")

