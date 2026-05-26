from xls_processor import process_xls
from color_logger import logger

def wrangle(src_dir="data", round_digits=4) -> list:
    logger.info("Starting data wrangling process...")
    processed_data = []
    raw_data = process_xls(src_dir=src_dir, round_digits=round_digits)
    for _, content in raw_data.items():
        for _, sheet_data in content.items():
            for _, rows in sheet_data.items():
                for row in rows:
                    data = {
                        "asset_name": row["asset_name"],
                        "date": row["opening_date"],
                        "opening_value": row["opening_value"],
                        "closing_value": row["closing_value"],
                        "period_yield": row["period_yield"],
                    }
                    processed_data.append(data)   
                    logger.debug(f"Processed #g<{data}>")
    logger.info(f"Data wrangling completed. Total records processed: #c<{len(processed_data)}>")
    return processed_data

def main():
    processed_data = wrangle(src_dir="data", round_digits=4)
    return processed_data

if __name__ == "__main__":
    main()
