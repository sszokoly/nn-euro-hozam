#!/usr/bin/env python3

from datetime import date, timedelta
from typing import Generator
from loguru import logger


def date_generator(
    start_date: str,
    end_date: str,
    interval: str = "daily"
) -> Generator[tuple[str, str], None, None]:
    incr = timedelta(days=1) if interval == "daily" else timedelta(weeks=1)
    
    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        logger.opt(colors=True).error(
            f"Invalid start date <yellow>{start_date}</yellow>"
        )
        return

    if start == date.today():
        logger.opt(colors=True).error(
            f"Start date <yellow>{start_date}</yellow> cannot be today"
        )
        return
    
    try:
        end = date.fromisoformat(end_date)
    except ValueError:
        logger.opt(colors=True).error(
            f"Invalid end date <yellow>{end_date}</yellow>"
        )
        return
    
    if end > date.today():
        logger.opt(colors=True).error(
            f"End date <yellow>{end_date}</yellow> cannot be in the future"
        )
        return

    if start > end:
        logger.opt(colors=True).error(
            f"Start date <yellow>{start_date}</yellow> must be before <yellow>{end_date}</yellow>"
        )
        return
    
    while start < date.fromisoformat(end_date):
        end = start + incr
        yield start.isoformat(), end.isoformat()
        start += incr


if __name__ == '__main__':
    from logger_config import setup_logging
    setup_logging()
    from loguru import logger
    
    dg = date_generator(start_date="2026-05-02", end_date="2026-05-08")
    for start_end in dg:
        print(start_end)