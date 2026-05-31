#!/usr/bin/env python3

import pandas as pd
from loguru import logger
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DF_DIR = BASE_DIR / "df"


def db_to_df_data(db_rows):
    """
    Convert database output data into a list of dictionaries suitable for DataFrame construction.
    """
    df_data = []
    for record in db_rows:
        df_record = {
            "asset_name": record[1],
            "date": record[2],
            "opening_value": record[3],
        }
        df_data.append(df_record)
    
    df = pd.DataFrame(df_data, columns=['asset_name', 'date', 'opening_value'])
    return df

if __name__ == "__main__":
    sample_db_rows = [
        ('1', 'Asset A', '2024-01-01', 100.0),
        ('2', 'Asset B', '2024-01-02', 150.0),
        ('3', 'Asset C', '2024-01-03', 200.0),
    ]
    
    df = db_to_df_data(sample_db_rows)
    print(df)
