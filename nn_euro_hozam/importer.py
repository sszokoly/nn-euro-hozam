#!/usr/bin/env python3

from loguru import logger
from database import Database
from xls_to_dict import xls_to_dict
from config import (
    DB_FILE,
    XLS_DIR,
    CSV_FILE,
    FIELD_NAMES,
    ROUND_DIGITS
)

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from multiprocessing.util import debug
from pathlib import Path


def value_moving_avg(df, days=50):
    df = df.copy()
    #df.sort_values(["asset", "closing_date"], inplace=True)
    
    df[f"value_ma_{days}d"] = (
        df.groupby("asset")["closing_euro_value"]
        .transform(lambda s: s.rolling(window=days, min_periods=days).mean())
    )
    return df


def yield_moving_avg(df, days=50):
    df = df.copy()
    #df.sort_values(["asset", "closing_date"], inplace=True)

    df[f"yield_ma_{days}d"] = (
        df.groupby("asset")["yield_ratio"]
        .transform(lambda s: s.rolling(window=days, min_periods=days).mean())
    )

    return df


def yield_ratio_cumprod(df, round_digit=ROUND_DIGITS):
    df["growth_factor"] = 1 + df["yield_ratio"]
    df["cumulative_growth"] = (
        df.groupby("asset")["growth_factor"]
          .cumprod()
          .round(decimals=round_digit)
    )
    df["yield_ratio_cumprod"] = (
        (df["cumulative_growth"] - 1)).round(decimals=round_digit)
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
            "yield_ratio": record["yield_ratio"]
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
            "yield_ratio": 0.0
        }))
    return ffilled_data


def data_to_dataframe(data):
    df = pd.DataFrame(data, columns=FIELD_NAMES)
    df = yield_ratio_cumprod(df)
    for days in [50, 100, 200]:
        df = value_moving_avg(df, days)
    for days in [50, 100, 200]:
        df = yield_moving_avg(df, days)
    # df["ma50_signal"] = np.where(
    #     df["value_ma_50d"] < df["closing_euro_value"],
    #     "🡻",
    #     "🢁"
    # )
    # df["ma100_signal"] = np.where(
    #     df["value_ma_100d"] < df["closing_euro_value"],
    #     "🡻",
    #     "🢁"
    # )
    # df["ma200_signal"] = np.where(
    #     df["value_ma_200d"] < df["closing_euro_value"],
    #     "🡻",
    #     "🢁"
    # )
    # df["ma50_200_signal"] = np.where(
    #     df["value_ma_50d"] > df["value_ma_200d"],
    #     "🢁",
    #     "🡻"
    # )
    for days in [50, 100, 200]:
        df[f"ma{days}_diff"] = (
            df[f"value_ma_{days}d"] - df["closing_euro_value"]
        )
        df[f"ma{days}_diff_ratio"] = (
            df[f"ma{days}_diff"] / df["closing_euro_value"]
        )
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
    yest_date = None
    
    for filepath in xls_files:
        logger.opt(colors=True).debug(f"Loading <yellow>{filepath}</yellow>")
        opening_date, closing_date, data = xls_to_dict(filepath, round_digits)
        
        if not opening_date and not closing_date:
            if yest_date:
                data = database.fetch_nn_by_date(yest_date.isoformat())
                data = ffill_data(data)
                database.insert(data)
                yest_date += timedelta(days=1)
            else:
                continue
        
        elif opening_date and closing_date:
            while yest_date and yest_date < opening_date - timedelta(days=1):
                data2 = database.fetch_nn_by_date(yest_date.isoformat())
                data2 = ffill_data(data2)
                database.insert(data2)
                yest_date += timedelta(days=1)
        
            if opening_date == yest_date:
                database.delete_nn_by_date(opening_date.isoformat())
        
            data = coerce_data(data)
            database.insert(data)
            yest_date = opening_date

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
    yest_date = database.end_date
    
    for file in files:
        
        filepath = Path(file).resolve()
        if not filepath.exists():
            continue
        
        logger.opt(colors=True).info(f"Loading <yellow>{filepath}</yellow>")
        opening_date, closing_date, data = xls_to_dict(filepath, round_digits)

        if not opening_date and not closing_date:
            if yest_date:
                data = database.fetch_nn_by_date(yest_date.isoformat())
                data = ffill_data(data)
                database.insert(data)
                yest_date += timedelta(days=1)
            else:
                continue

        elif opening_date and closing_date:
            while yest_date and yest_date < opening_date:# - timedelta(days=1):
                data2 = database.fetch_nn_by_date(yest_date.isoformat())
                data2 = ffill_data(data2)
                database.insert(data2)
                yest_date += timedelta(days=1)
        
            if opening_date == yest_date:
                database.delete_nn_by_date(opening_date.isoformat())
        
            data = coerce_data(data)
            database.insert(data)
            yest_date = opening_date

    data = database.fetchall()
    df = data_to_dataframe(data)
    df.to_csv(csv_file, index=False)
    return df


if __name__ == '__main__':
    from config import setup_logging
    setup_logging()
    from loguru import logger
    from database import Database

    import_nn_from_xls()
    #df = merge_xls_with_nn(["data/xls/NN_eszkozalap_hozamok_2026-06-07_2026-06-08.xls"])
    
