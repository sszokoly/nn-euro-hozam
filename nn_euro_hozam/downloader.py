#!/usr/bin/env python3

from loguru import logger

import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from queue import Queue
from random import randint
from threading import Event
import traceback

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
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
DIAGNOSTIC_BUNDLE_LIMIT = 10
DEBUG_DIR = Path(__file__).parent / "data" / "debug"

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
    table_container = "#_yieldchartportlet_WAR_nnportlet_tableContainer"
    yield_submit_button = "#_yieldchartportlet_WAR_nnportlet_yieldChartSubmitButton"
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
    table_download_container = (
        "#_yieldchartportlet_WAR_nnportlet_downloaderButtonInTableView"
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


def _read_yield_page_state(driver: WebDriver) -> dict:
    return driver.execute_script(
        """
        const product = document.querySelector(arguments[0]);
        const fromDate = document.querySelector(arguments[1]);
        const toDate = document.querySelector(arguments[2]);
        const table = document.querySelector(arguments[3]);
        const downloadContainer = document.querySelector(arguments[4]);
        const downloadButton = document.querySelector(arguments[5]);

        const visible = element => {
            if (!element) return false;
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' &&
                rect.width > 0 && rect.height > 0;
        };

        return {
            productValue: product ? product.value : null,
            productText: product && product.selectedOptions.length
                ? product.selectedOptions[0].textContent.trim() : null,
            fromDate: fromDate ? fromDate.value : null,
            toDate: toDate ? toDate.value : null,
            tableVisible: visible(table),
            downloadContainerVisible: visible(downloadContainer),
            downloadButtonVisible: visible(downloadButton),
            downloadButtonEnabled: Boolean(downloadButton) && !downloadButton.disabled,
        };
        """,
        Selectors.product_select,
        Selectors.from_date_input,
        Selectors.to_date_input,
        Selectors.table_container,
        Selectors.table_download_container,
        Selectors.table_download_button,
    )


def _wait_for_requested_inputs(
    driver: WebDriver, start: DateParts, end: DateParts
) -> None:
    expected = {
        "productValue": PRODUCT_VALUE,
        "productText": PRODUCT_NAME,
        "fromDate": start.display_value,
        "toDate": end.display_value,
    }
    last_state = None

    def inputs_match(active_driver: WebDriver) -> bool:
        nonlocal last_state
        last_state = _read_yield_page_state(active_driver)
        return all(last_state.get(key) == value for key, value in expected.items())

    try:
        WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(inputs_match)
    except TimeoutException as exc:
        raise RuntimeError(
            "NN did not apply requested product/date state "
            f"for {PRODUCT_NAME} ({PRODUCT_VALUE}), "
            f"{start.display_value} to {end.display_value}: {last_state}"
        ) from exc


def _wait_for_table_download_ready(
    driver: WebDriver, start: DateParts, end: DateParts
) -> None:
    last_state = None

    def download_is_ready(active_driver: WebDriver) -> bool:
        nonlocal last_state
        last_state = _read_yield_page_state(active_driver)
        return all(
            last_state.get(key)
            for key in (
                "tableVisible",
                "downloadContainerVisible",
                "downloadButtonVisible",
                "downloadButtonEnabled",
            )
        )

    try:
        WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(download_is_ready)
    except TimeoutException as exc:
        raise RuntimeError(
            "NN did not expose a usable XLS download control "
            f"for {PRODUCT_NAME} ({PRODUCT_VALUE}), "
            f"{start.display_value} to {end.display_value}: {last_state}"
        ) from exc


def _submit_yield_form(driver: WebDriver, start: DateParts, end: DateParts) -> None:
    def submit_if_ready(active_driver: WebDriver) -> bool:
        try:
            button = active_driver.find_element(
                By.CSS_SELECTOR, Selectors.yield_submit_button
            )
            if not button.is_displayed() or not button.is_enabled():
                return False
            button.click()
            return True
        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(submit_if_ready)
    except TimeoutException as exc:
        raise RuntimeError(
            "NN did not expose an enabled yield-form submit control "
            f"for {PRODUCT_NAME} ({PRODUCT_VALUE}), "
            f"{start.display_value} to {end.display_value}"
        ) from exc


def _click_table_download(driver: WebDriver, start: DateParts, end: DateParts) -> None:
    def click_ready_download(active_driver: WebDriver) -> bool:
        try:
            button = active_driver.find_element(
                By.CSS_SELECTOR, Selectors.table_download_button
            )
            if not button.is_displayed() or not button.is_enabled():
                return False
            button.click()
            return True
        except StaleElementReferenceException:
            return False

    try:
        WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(click_ready_download)
    except TimeoutException as exc:
        raise RuntimeError(
            "NN could not click a usable XLS download control "
            f"for {PRODUCT_NAME} ({PRODUCT_VALUE}), "
            f"{start.display_value} to {end.display_value}"
        ) from exc


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

        if (typeof window._yieldchartportlet_WAR_nnportlet_toggleButtonAndLabelState === 'function') {
            window._yieldchartportlet_WAR_nnportlet_toggleButtonAndLabelState();
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


def _control_state(driver: WebDriver, selector: str) -> dict:
    return driver.execute_script(
        """
        const element = document.querySelector(arguments[0]);
        if (!element) {
            return { selector: arguments[0], found: false };
        }

        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return {
            selector: arguments[0],
            found: true,
            tagName: element.tagName,
            text: element.textContent.trim(),
            disabled: Boolean(element.disabled),
            visible: style.display !== 'none' && style.visibility !== 'hidden' &&
                rect.width > 0 && rect.height > 0,
            outerHtml: element.outerHTML,
            bounds: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        };
        """,
        selector,
    )


def _prune_diagnostic_bundles(debug_dir: Path) -> None:
    bundles = sorted(
        (item for item in debug_dir.iterdir() if item.is_dir()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for bundle in bundles[DIAGNOSTIC_BUNDLE_LIMIT:]:
        shutil.rmtree(bundle)


def _capture_failure_diagnostics(
    driver: WebDriver,
    exception: Exception,
    start_date: date,
    end_date: date,
    attempt_number: int,
) -> Path | None:
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        bundle = DEBUG_DIR / (
            f"failure-{datetime.now().strftime('%Y%m%dT%H%M%S_%f')}-"
            f"attempt-{attempt_number}"
        )
        bundle.mkdir()
    except OSError as capture_error:
        logger.opt(colors=False).error(
            "Unable to create Selenium diagnostic bundle: {}", capture_error
        )
        return None

    collection_errors = {}
    metadata = {
        "attempt_number": attempt_number,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "exception": str(exception),
        "collection_errors": collection_errors,
    }

    try:
        (bundle / "exception.txt").write_text(
            "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            ),
            encoding="utf-8",
        )
    except OSError as capture_error:
        collection_errors["exception"] = str(capture_error)

    def collect(name: str, collector) -> None:
        try:
            metadata[name] = collector()
        except Exception as capture_error:
            collection_errors[name] = str(capture_error)

    collect("url", lambda: driver.current_url)
    collect("title", lambda: driver.title)
    collect("capabilities", lambda: driver.capabilities)
    collect("controls", lambda: {
        "table_view_button": _control_state(driver, Selectors.table_view_button),
        "asset_funds_checkbox_group": _control_state(
            driver, Selectors.asset_funds_checkbox_group
        ),
        "table_download_button": _control_state(
            driver, Selectors.table_download_button
        ),
    })

    try:
        if not driver.save_screenshot(str(bundle / "screenshot.png")):
            raise RuntimeError("Browser did not save a screenshot")
    except Exception as capture_error:
        collection_errors["screenshot"] = str(capture_error)

    try:
        (bundle / "page.html").write_text(driver.page_source, encoding="utf-8")
    except Exception as capture_error:
        collection_errors["page_html"] = str(capture_error)

    try:
        (bundle / "browser-console.json").write_text(
            json.dumps(driver.get_log("browser"), indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as capture_error:
        collection_errors["browser_console"] = str(capture_error)

    try:
        (bundle / "metadata.json").write_text(
            json.dumps(metadata, indent=2, default=str), encoding="utf-8"
        )
    except OSError as capture_error:
        logger.opt(colors=False).error(
            "Unable to save Selenium diagnostic metadata in {}: {}",
            bundle,
            capture_error,
        )

    try:
        _prune_diagnostic_bundles(DEBUG_DIR)
    except OSError as capture_error:
        logger.opt(colors=False).error(
            "Unable to prune Selenium diagnostic bundles: {}", capture_error
        )

    return bundle


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
    attempt_number: int = 1,
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
            _wait_for_requested_inputs(driver, start_parts, end_parts)

            _select_all_asset_funds(driver)
            _submit_yield_form(driver, start_parts, end_parts)

            WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, Selectors.table_view_button)
                )
            ).click()
            _wait_for_table_download_ready(driver, start_parts, end_parts)
            _click_table_download(driver, start_parts, end_parts)

            downloaded_file = _wait_for_download(download_dir)
        except Exception as exception:
            diagnostic_bundle = _capture_failure_diagnostics(
                driver,
                exception,
                resolved_start_date,
                resolved_end_date,
                attempt_number,
            )
            if diagnostic_bundle is not None:
                exception.add_note(f"Selenium diagnostics saved to {diagnostic_bundle}")
            raise
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
    progress_queue: Queue = None,
    result_queue: Queue = None,
    stop_event: Event = Event(),
):

    outfile_path = Path(outfile_path).resolve() if outfile_path else Path.cwd()

    logger.opt(colors=True).info(f"Start date: <yellow>{start_date}</yellow>")

    try:
        while not stop_event.is_set():
            try:
                resolved_start_date, resolved_end_date = _resolve_dates(start_date, end_date)
            except Exception as e:
                logger.opt(colors=True).error(f"Invalid date: {e}")
                return

            if (
                resolved_end_date > date.today() or
                resolved_start_date >= resolved_end_date
            ):
                logger.opt(colors=True).error(f"Invalid {start_date} or {end_date}")
                return

            if interval == "daily":
                resolved_interval = timedelta(days=1)
            elif interval == "weekly":
                resolved_interval = timedelta(days=7)
            else:
                logger.opt(colors=True).error(f"Invalid interval {interval}")
                return

            start = resolved_start_date
            end = start + resolved_interval
            total_intervals = (resolved_end_date - resolved_start_date) / resolved_interval
            interval_count = 0
            downloaded_files = []

            while start < resolved_end_date:
                if start != resolved_start_date:
                    stop_event.wait(timeout=min_sleep_secs)

                attempt = 0
                while attempt < retries:
                    start_end = f"{start.isoformat()} - {end.isoformat()}"
                    try:
                        logger.opt(colors=True).info(
                            f"Download attempt for {start_end} "
                            f"to <yellow>{outfile_path}</yellow>"
                        )
                        
                        #output_path = f"test_{start_end}"
                        output_path = download_xls(
                            start_date=start.isoformat(),
                            end_date=end.isoformat(),
                            outfile_path=outfile_path,
                            append_timestamp=append_timestamp,
                            attempt_number=attempt + 1,
                        )
                        
                        downloaded_files.append(output_path)
                        
                        logger.opt(colors=True).info(
                            f"Download <green>success</green> for {start_end} "
                            f"to <yellow>{output_path}</yellow>, "
                            f"sleep <cyan>{min_sleep_secs}</cyan> secs"
                        )
                        
                        start += resolved_interval
                        end += resolved_interval
                        interval_count += 1
                        
                        if progress_queue and not progress_queue.full():
                            pct = int(interval_count / total_intervals * 100)
                            progress_queue.put(pct)
                            logger.opt(colors=True).info(
                                f"Put <cyan>{pct}</cyan> in the progress_queue"
                            )
                        break
                    
                    except Exception as e:
                        diagnostic_bundle = next(
                            (
                                note.removeprefix("Selenium diagnostics saved to ")
                                for note in getattr(e, "__notes__", [])
                                if note.startswith("Selenium diagnostics saved to ")
                            ),
                            None,
                        )
                        logger.opt(colors=False).debug(
                            "Exception in download for {}: {}", start_end, e
                        )
                        if diagnostic_bundle:
                            logger.opt(colors=False).error(
                                "Selenium diagnostics for {} saved to {}",
                                start_end,
                                diagnostic_bundle,
                            )
                        
                        attempt += 1
                        if attempt < retries:
                            sleep_sec = min_sleep_secs + randint(1, min_sleep_secs)
                            
                            logger.opt(colors=True).error(
                                f"Download <red>failed</red>  for {start_end} "
                                f"on attempt <cyan>{attempt}</cyan>, "
                                f"sleep <cyan>{sleep_sec:>3}</cyan> secs..."
                            )
                            stop_event.wait(timeout=sleep_sec)
                        
                        else:
                            logger.opt(colors=True).error(
                                f"Download <red>failed</red>  for {start_end} "
                                f"after <cyan>{retries}</cyan> attempts."
                            )
            stop_event.set()
    finally:
        if progress_queue:
            progress_queue.put("done")
            logger.opt(colors=True).info("Put <cyan>done</cyan> in the progress_queue")
        if result_queue:
            result_queue.put(downloaded_files)


if __name__ == "__main__":
    from logger_config import setup_logging
    setup_logging()
    from loguru import logger
    import argparse
    
    # import sys
    # pq = Queue()
    # sys.argv.extend([
    #     "--start-date", "2026-06-06",
    #     "--end-date", "2026-06-09",
    #     "--min-sleep-secs", "2"
    # ])

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
