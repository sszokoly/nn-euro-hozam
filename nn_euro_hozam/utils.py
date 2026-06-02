#!/usr/bin/env python3

from datetime import date, datetime, timedelta
from typing import Generator
from loguru import logger

def generate_dates(
    start_date: str,
    end_date: str,
    interval: str = "daily"
) -> Generator[tuple[str, str], None, None]:
    incr = timedelta(days=1) if interval == "daily" else timedelta(weeks=1)
    
    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        logger.opt(colors=True).error(
            f"Invalid start date or format: <yellow>{start_date}</yellow>"
        )
        return

    if start == date.today():
        logger.opt(colors=True).error(
            f"Start date cannot be today: <yellow>{start_date}</yellow>"
        )
        return
    
    try:
        end = date.fromisoformat(end_date)
    except ValueError:
        logger.opt(colors=True).error(
            f"Invalid end date or format: <yellow>{end_date}</yellow>"
        )
        return
    
    if end > date.today():
        logger.opt(colors=True).error(
            f"End date cannot be in the future: <yellow>{end_date}</yellow>"
        )
        return

    if start > end:
        logger.opt(colors=True).error(
            f"Start date cannot be after end date: <yellow>{start_date}</yellow> > <yellow>{end_date}</yellow>"
        )
        return
    
    while start < date.fromisoformat(end_date):
        end = start + incr
        yield start.isoformat(), end.isoformat()
        start += incr