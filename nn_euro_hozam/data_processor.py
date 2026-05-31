import pandas as pd
from loguru import logger
from pathlib import Path
from nn_euro_hozam.db import Database
from nn_euro_hozam.xls_to_dict import xls_to_dict


def import_xls_data(src_dir=None, round_digits=4) -> list:
    logger.info("Starting to process XLS data...")
    xls_data = []
    for filename in Path(src_dir).glob("*.xls"):
        raw_data = xls_to_dict(filename=filename, round_digits=round_digits)
        for _, content in raw_data.items():
            for _, rows in content.items():
                for row in rows:
                    data = {
                        "asset_name": row["asset_name"],
                        "date": row["opening_date"],
                        "opening_value": row["opening_value"],
                        "closing_value": row["closing_value"],
                        "period_yield": row["period_yield"],
                    }
                    xls_data.append(data)   
                    logger.debug(f"Processed <green>{data}</green>")
    logger.opt(colors=True).info(f"XLS data processing completed. Total number of records: <cyan>{len(xls_data)}</cyan>")
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
        db.insert(xls_data)
        db.backup()
    data = db.fetchall()
    df = pd.DataFrame.from_records(
        data,
        columns=["id", "asset_name", "date", "opening_value", "closing_value", "period_yield"]
    )
    df = df.drop(columns=["id"])
    df = df.set_index('date')
    df = df.sort_index()
    df.index = pd.to_datetime(df.index)
    return df



if __name__ == "__main__":
    df = get_df_from_db()
    print(df.head())
