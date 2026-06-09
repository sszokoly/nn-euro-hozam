#!/usr/bin/env python3

import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from loguru import logger
from pathlib import Path
from random import randint
from queue import Queue
from utils import date_generator

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


TARGET_URL = "https://www.nn.hu/hozamszamlalo"
PRODUCT_NAME = "Euro Alap rendszeres díjas"
PRODUCT_VALUE = "31866"

DEFAULT_TIMEOUT_SECONDS = 30
DOWNLOAD_TIMEOUT_SECONDS = 60

class Selectors:
    accept_cookies_button = "#onetrust-accept-btn-handler"
    product_select = "#_yieldchartportlet_WAR_nnportlet_selectedProduct"
    from_date_input = "#_yieldchartportlet_WAR_nnportlet_displayedPeriodFrom"
    from_date_day = "#_yieldchartportlet_WAR_nnportlet_displayedPeriodFromDay"
    from_date_month = "#_yieldchartportlet_WAR_nnportlet_displayedPeriodFromMonth"
    from_date_year = "#_yieldchartportlet_WAR_nnportlet_displayedPeriodFromYear"
    to_date_input = "#_yieldchartportlet_WAR_nnportlet_displayedPeriodTo"
    to_date_day = "#_yieldchartportlet_WAR_nnportlet_displayedPeriodToDay"
    to_date_month = "#_yieldchartportlet_WAR_nnportlet_displayedPeriodToMonth"
    to_date_year = "#_yieldchartportlet_WAR_nnportlet_displayedPeriodToYear"
    date_set_by_user = "#_yieldchartportlet_WAR_nnportlet_dateSetByUser"
    table_view_button = "#_yieldchartportlet_WAR_nnportlet_yieldChartShowTable"
    asset_funds_checkbox_group = (
        "#_yieldchartportlet_WAR_nnportlet_assetFundsCheckboxGroup"
    )
    asset_fund_checkboxes = (
        "#_yieldchartportlet_WAR_nnportlet_assetFundsCheckboxGroup "
        'input[type="checkbox"]'
    )
    selected_all = "#_yieldchartportlet_WAR_nnportlet_selectedAll"
    select_all_label = "#_yieldchartportlet_WAR_nnportlet_select-all-checkbox-label"
    table_download_button = (
        "#_yieldchartportlet_WAR_nnportlet_downloaderButtonInTableView button"
    )


@dataclass(frozen=True)
class DateParts:
    display_value: str
    day: str
    month_index: str
    year: str


def _coerce_date(value: date | datetime | str | None, name: str) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO date or datetime string") from exc

    raise TypeError(f"{name} must be a datetime, date, ISO date string, or None")


def _resolve_dates(
    start_date: date | datetime | str | None,
    end_date: date | datetime | str | None,
) -> tuple[date, date]:
    resolved_end_date = _coerce_date(end_date, "end_date") or (
        date.today() - timedelta(days=1)
    )
    resolved_start_date = _coerce_date(start_date, "start_date") or (
        resolved_end_date - timedelta(days=7)
    )

    if resolved_start_date > resolved_end_date:
        raise ValueError("start_date must be on or before end_date")

    return resolved_start_date, resolved_end_date


def _to_hungarian_date_parts(value: date) -> DateParts:
    return DateParts(
        display_value=f"{value.year}. {value.month:02d}. {value.day:02d}.",
        day=str(value.day),
        month_index=str(value.month - 1),
        year=str(value.year),
    )


def _build_driver(download_dir: Path) -> WebDriver:
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,720")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(download_dir)},
    )
    return driver


def _wait_for_css(
    driver: WebDriver,
    selector: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> WebElement:
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def _click_if_visible(driver: WebDriver, selector: str, timeout: int = 5) -> None:
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
    except TimeoutException:
        return

    element.click()


def _select_product(driver: WebDriver) -> None:
    selected_value = driver.execute_script(
        """
        const selector = arguments[0];
        const productName = arguments[1];
        const productValue = arguments[2];
        const select = document.querySelector(selector);

        if (!select) {
            throw new Error(`Product select not found: ${selector}`);
        }

        const option = Array.from(select.options).find(
            item => item.value === productValue && item.textContent.trim() === productName
        );

        if (!option) {
            throw new Error(`Product option not found: ${productName} (${productValue})`);
        }

        select.value = option.value;
        select.dispatchEvent(new Event('input', { bubbles: true }));
        select.dispatchEvent(new Event('change', { bubbles: true }));

        if (typeof window._yieldchartportlet_WAR_nnportlet_productOnChange === 'function') {
            window._yieldchartportlet_WAR_nnportlet_productOnChange();
        }

        return select.value;
        """,
        Selectors.product_select,
        PRODUCT_NAME,
        PRODUCT_VALUE,
    )

    if selected_value != PRODUCT_VALUE:
        raise RuntimeError(
            f"Expected selected product {PRODUCT_VALUE}, got {selected_value}"
        )


def _set_date(
    driver: WebDriver,
    input_selector: str,
    day_selector: str,
    month_selector: str,
    year_selector: str,
    value: DateParts,
) -> None:
    driver.execute_script(
        """
        const input = document.querySelector(arguments[0]);
        const dayInput = document.querySelector(arguments[1]);
        const monthInput = document.querySelector(arguments[2]);
        const yearInput = document.querySelector(arguments[3]);
        const dateSetByUserInput = document.querySelector(arguments[4]);
        const displayValue = arguments[5];
        const day = arguments[6];
        const monthIndex = arguments[7];
        const year = arguments[8];

        if (!input || !dayInput || !monthInput || !yearInput) {
            throw new Error(`Date input set is incomplete for ${arguments[0]}`);
        }

        input.value = displayValue;
        input.setAttribute('value', displayValue);
        dayInput.value = day;
        monthInput.value = monthIndex;
        yearInput.value = year;

        if (dateSetByUserInput) {
            dateSetByUserInput.value = 'true';
        }

        for (const eventName of ['input', 'change', 'blur']) {
            input.dispatchEvent(new Event(eventName, { bubbles: true }));
        }
        """,
        input_selector,
        day_selector,
        month_selector,
        year_selector,
        Selectors.date_set_by_user,
        value.display_value,
        value.day,
        value.month_index,
        value.year,
    )


def _select_all_asset_funds(driver: WebDriver) -> None:
    _wait_for_css(driver, Selectors.asset_funds_checkbox_group)
    WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(
        lambda active_driver: (
            len(
                active_driver.find_elements(
                    By.CSS_SELECTOR, Selectors.asset_fund_checkboxes
                )
            )
            > 0
        )
    )

    selected_count = driver.execute_script(
        """
        const checkboxes = Array.from(document.querySelectorAll(arguments[0]));
        const selectedAllInput = document.querySelector(arguments[1]);
        const selectAllLabel = document.querySelector(arguments[2]);

        for (const checkbox of checkboxes) {
            checkbox.checked = true;
            checkbox.setAttribute('checked', 'checked');
            checkbox.dispatchEvent(new Event('change', { bubbles: true }));
        }

        if (selectedAllInput) {
            selectedAllInput.value = '0';
        }

        if (selectAllLabel) {
            selectAllLabel.textContent = 'Kijelölések megszüntetése';
        }

        return checkboxes.filter(checkbox => checkbox.checked).length;
        """,
        Selectors.asset_fund_checkboxes,
        Selectors.selected_all,
        Selectors.select_all_label,
    )

    if not isinstance(selected_count, int) or selected_count <= 0:
        raise RuntimeError("No asset fund checkboxes were selected")


def _wait_for_download(
    download_dir: Path, timeout: int = DOWNLOAD_TIMEOUT_SECONDS
) -> Path:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        downloading_files = list(download_dir.glob("*.crdownload")) + list(
            download_dir.glob("*.tmp")
        )
        completed_files = [
            item
            for item in download_dir.iterdir()
            if item.is_file() and item.suffix not in {".crdownload", ".tmp"}
        ]

        if completed_files and not downloading_files:
            newest_file = max(completed_files, key=lambda item: item.stat().st_mtime)
            if newest_file.stat().st_size > 0:
                return newest_file

        time.sleep(0.5)

    raise TimeoutError(f"Download did not complete within {timeout} seconds")


def _resolve_outfile_path(
    downloaded_file: Path, outfile_path: str | Path | None
) -> Path:
    if outfile_path is None:
        return Path.cwd() / downloaded_file.name

    destination = Path(outfile_path).expanduser()
    raw_outfile_path = str(outfile_path)
    if destination.is_dir() or raw_outfile_path.endswith(("/", "\\")):
        return destination / downloaded_file.name

    return destination


def download_xls(
    start_date: date | datetime | str | None = None,
    end_date: date | datetime | str | None = None,
    outfile_path: str | Path | None = None,
    append_timestamp: bool = False,
) -> Path:
    """Download NN Euro Alap yield spreadsheet using headless Selenium Chromium.

    If dates are omitted, the range defaults to the last seven days ending yesterday.
    If outfile_path is omitted, the browser-provided filename is saved in the current directory.
    """

    resolved_start_date, resolved_end_date = _resolve_dates(start_date, end_date)
    start_parts = _to_hungarian_date_parts(resolved_start_date)
    end_parts = _to_hungarian_date_parts(resolved_end_date)
    
    with tempfile.TemporaryDirectory(prefix="nn-euro-hozam-") as tmpdir:
        download_dir = Path(tmpdir)
        driver = _build_driver(download_dir)

        try:
            driver.get(TARGET_URL)
            _click_if_visible(driver, Selectors.accept_cookies_button)
            _wait_for_css(driver, Selectors.product_select)

            _select_product(driver)
            _set_date(
                driver,
                Selectors.from_date_input,
                Selectors.from_date_day,
                Selectors.from_date_month,
                Selectors.from_date_year,
                start_parts,
            )
            _set_date(
                driver,
                Selectors.to_date_input,
                Selectors.to_date_day,
                Selectors.to_date_month,
                Selectors.to_date_year,
                end_parts,
            )

            WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, Selectors.table_view_button)
                )
            ).click()
            _select_all_asset_funds(driver)

            WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, Selectors.table_download_button)
                )
            ).click()

            downloaded_file = _wait_for_download(download_dir)
        finally:
            driver.quit()

        destination = _resolve_outfile_path(downloaded_file, outfile_path)
        
        if append_timestamp:
            start = start_parts.display_value.replace(". ", "-").rstrip(".")
            end = end_parts.display_value.replace(". ", "-").rstrip(".")
            timestamp = f"{start}_{end}"
            destination = destination.with_name(
                f"{destination.stem}_{timestamp}{destination.suffix}"
            )
        
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(downloaded_file), destination)

    if destination.stat().st_size <= 0:
        raise RuntimeError(f"Downloaded file is empty: {destination}")

    return destination


def download_multiple_xls(
    start_date: str,
    end_date: str,
    interval: str = "daily",
    retries: int = 20,
    min_sleep_secs: int = 30,
    outfile_path: Path = None,
    append_timestamp: bool = True,
    queue: Queue = None
):

    outfile_path = Path(outfile_path).resolve() if outfile_path else Path.cwd()

    for start, end in date_generator(start_date, end_date, interval):
        if start != start_date:
            time.sleep(min_sleep_secs)

        attempt = 0
        while attempt < retries:
            start_end = f"{start} - {end}"
            try:
                logger.opt(colors=True).info(
                    f"Download attempt for {start_end} "
                    f"to <yellow>{outfile_path}</yellow>"
                )
                
                output_path = download_xls(
                    start_date=start,
                    end_date=end,
                    outfile_path=outfile_path,
                    append_timestamp=append_timestamp
                )
                
                logger.opt(colors=True).info(
                    f"Download <green>success</green> for {start_end} "
                    f"to <yellow>{output_path}</yellow> "
                    f"- sleep <cyan>{min_sleep_secs}</cyan> secs"
                )
                
                if queue and not queue.full():
                    queue.put(
                        f"Download success for {output_path}, "
                        f"trying next in  {min_sleep_secs:>3}secs"
                    )
                break
            
            except Exception as e:
                logger.opt(colors=True).debug(
                    f"Exception in download for {start_end}: <red>{e}</red>"
                )
                
                attempt += 1
                if attempt < retries:
                    sleep_sec = min_sleep_secs + randint(1, min_sleep_secs)
                    
                    logger.opt(colors=True).error(
                        f"Download <red>failed</red>  for {start_end} "
                        f"on attempt <cyan>{attempt}</cyan> "
                        f"- sleep <cyan>{sleep_sec:>3}</cyan> secs..."
                    )
                    
                    if queue and not queue.full():
                        queue.put(
                            f"Download failed, "
                            f"trying again in {sleep_sec:>3}secs"
                        )
                    time.sleep(sleep_sec)
                
                else:
                    logger.opt(colors=True).error(
                        f"Download <red>failed</red>  for {start_end} "
                        f"after <cyan>{retries}</cyan> attempts."
                    )
                    

if __name__ == "__main__":
    from logger_config import setup_logging
    setup_logging()
    from loguru import logger
    import argparse

    parser = argparse.ArgumentParser(
        description="Download NN Euro Alap rendszeres díjas yield spreadsheets."
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(date.today() - timedelta(days=2)).isoformat(),
        required=False,
        help="Start date as ISO date, for example '2026-05-10'.\
              Defaults to the day before yesterday.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=date.today().isoformat(),
        required=False,
        help="End date as ISO date, for example '2026-05-17'.\
              Defaults to today.",
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
        type=Path,
        default=Path("data/xls/"),
        required=False,
        help="Destination file path, including folder and filename.\
              Defaults to the browser-provided filename in the current directory.",
    )
    parser.add_argument(
        "--append-timestamp",
        action="store_true",
        default=True,
        required=False,
        help="Append a timestamp to the output filename.",
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
    args = parser.parse_args()
    
    output_path = download_multiple_xls(
        start_date=args.start_date,
        end_date=args.end_date,
        interval=args.interval,
        retries=args.retries,
        min_sleep_secs=args.min_sleep_secs,
        outfile_path=args.outfile_path,
        append_timestamp=args.append_timestamp,

    )
    print(output_path)
