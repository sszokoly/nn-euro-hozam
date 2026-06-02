#!/usr/bin/env python3

import pandas as pd
from loguru import logger
from pathlib import Path
from nn_euro_hozam.db import Database
from nn_euro_hozam.xls_to_dict import xls_to_dict
from utils import generate_dates


def ffill_xls_data(xls_data):
    data = []
    gd = generate_dates(
        start_date=sorted(xls_data.keys())[0],
        end_date=sorted(xls_data.keys())[-1],
        interval="daily"
    )

    for start, _ in gd:
        rows = xls_data.get(start)
        if rows:
            data.append(rows)
            continue
        last_records = data[-1]
        ffilled_record = []
        for record in last_records:
            for key, value in record.items():
                if key in ["opening_date", "closing_date"]:
                    record[key] = start
                elif key in ["opening_value", "closing_value"]:
                    record[key] = record["closing_value"]
                elif key == "period_yield":
                    record[key] = 0
            ffilled_record.append(record)
        data.append(ffilled_record)
    return data


def listify_xls_data(xls_data):
    listified_data = []
    for records in xls_data:
        for record in records:
            data = [
                record["asset_name"],
                record["opening_date"],
                record["opening_value"],
                record["closing_value"],
                record["period_yield"]
            ]
            listified_data.append(data)
    return listified_data


def import_xls_data(src_dir=None, round_digits=4) -> list:
    logger.info("Starting to process XLS data...")
    xls_data = {}
    for filename in sorted(Path(src_dir).glob("*.xls")):
        opening_date, rows = xls_to_dict(filename=filename, round_digits=round_digits)
        if opening_date:
            xls_data[opening_date] = rows
    return xls_data


def get_df_from_db(
    db="nn_euro_yields.db",
    table="nn_euro_yields",
    src_dir=Path.cwd() / "data" / "xls",
    round_digits=4,
    init_db=False
) -> list:
    db = Database(db=db, table=table, init_db=init_db)
    
    if init_db:
        xls_data = import_xls_data(src_dir=src_dir, round_digits=round_digits)
        xls_data = ffill_xls_data(xls_data)
        data = listify_xls_data(xls_data)
        db.insert(data)
        db.backup()

    data = db.fetchall()
    df = pd.DataFrame.from_records(
        data,
        columns=["id", "asset_name", "date", "opening_value", "closing_value", "period_yield"]
    )
    df = df.set_index('id')
    df = df.sort_values(by="date").reset_index(drop=True)
    return df



if __name__ == "__main__":
    df = get_df_from_db()
    print(df.head())
