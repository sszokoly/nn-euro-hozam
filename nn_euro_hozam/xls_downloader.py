import argparse
import asyncio
from datetime import date, timedelta
from web_scraper import download_yields_xls
from random import randint
from typing import Generator
from loguru import logger

def _generate_start_end_dates(
    start_date: str,
    end_date: str,
    interval: str = "daily"
) -> Generator[tuple[str, str], None, None]:
    incr = timedelta(days=1) if interval == "daily" else timedelta(weeks=1)
    
    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        logger.error(f"Invalid start date or format: #r<{start_date}>")
        return

    if start == date.today():
        logger.error(f"Start date cannot be today: #r<{start_date}>")
        return
    
    try:
        end = date.fromisoformat(end_date)
    except ValueError:
        logger.error(f"Invalid end date or format: #r<{end_date}>")
        return
    
    if end > date.today():
        logger.error(f"End date cannot be in the future: #r<{end_date}>")
        return

    if start > end:
        logger.error(f"Start date cannot be after end date: #r<{start_date}> > #r<{end_date}>")
        return
    
    while start < date.fromisoformat(end_date):
        end = start + incr
        yield start.isoformat(), end.isoformat()
        start += incr


async def download(
    start_date: str,
    end_date: str,
    interval: str = "daily",
    retries: int = 20,
    min_sleep_secs: int = 30,
    outfile_path: str = "data/",
):

    for start, end in _generate_start_end_dates(start_date, end_date, interval):
        if start != start_date:
            await asyncio.sleep(min_sleep_secs)

        attempt = 0
        while attempt < retries:
            start_end = f"#y<{start}> - #y<{end}>"
            try:
                output_path = await asyncio.to_thread(
                    download_yields_xls,
                    start_date=start,
                    end_date=end,
                    append_timestamp=True,
                    outfile_path=outfile_path
                )
                logger.opt(colors=True).info(f"Download <green>success</green> for {start_end} to <yellow>{output_path}</yellow> - sleep <cyan>{min_sleep_secs}</cyan> secs")
                break
            except Exception as exc:
                logger.debug(f"Exception during download for {start_end}: {exc}")
                attempt += 1
                if attempt < retries:
                    sleep_sec = min_sleep_secs + randint(1, min_sleep_secs)
                    logger.error(f"Download <red>failed</red>  for {start_end} on attempt <cyan>{attempt}</cyan> - sleep <cyan>{sleep_sec:>3}</cyan> secs...")
                    await asyncio.sleep(sleep_sec)
                else:
                    logger.error(f"Download <red>failed</red>  for {start_end} after <cyan>{retries}</cyan> attempts.")
                    

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download NN Euro Yields Spreadsheets for a specified date range."
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date as ISO date, for example 2026-05-10.\
              Defaults to seven days before end date.",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date as ISO date, for example 2026-05-17.\
              Defaults to yesterday.",
    )
    parser.add_argument(
        "--interval",
        required=False,
        default="daily",
        help="Interval for downloading yields, 'daily' or 'weekly'.\
              Defaults to 'daily'.",
    )
    parser.add_argument(
        "--outfile-path",
        required=False,
        default="data/",
        help="Destination file path, including folder and filename.\
              Defaults to data/ folder.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=20,
        required=False,
        help="Number of retry attempts for downloading yields.",
    )
    parser.add_argument(
        "--min-sleep-secs",
        type=int,
        default=30,
        required=False,
        help="Minimum number of seconds to sleep between retry attempts.",
    )
    return parser.parse_args()

async def main():
    args = _parse_args()
    await download(
        start_date=args.start_date,
        end_date=args.end_date,
        interval=args.interval,
        retries=args.retries,
        min_sleep_secs=args.min_sleep_secs,
        outfile_path = args.outfile_path,
    )

if __name__ == "__main__":
    import sys
    sys.argv.extend([
        "--start-date", "2025-09-01",
        "--end-date", "2025-09-10",
        "--interval", "daily",
        "--outfile-path", "data/",
        "--retries", "20",
        "--min-sleep-secs", "30",
    ])
    asyncio.run(main())
