#!/usr/bin/env python3

from loguru import logger

import shutil
import tempfile
import time
from dataclasses import dataclass
from contextvars import ContextVar
from datetime import date, datetime, timedelta
import json
import math
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
NAVIGATION_TIMEOUT_SECONDS = 60
COMMAND_TIMEOUT_SECONDS = 120
DOWNLOAD_TIMEOUT_SECONDS = 60
DIAGNOSTIC_BUNDLE_LIMIT = 10
DEBUG_DIR = Path(__file__).parent / "data" / "debug"
_CURRENT_ATTEMPT = ContextVar("yield_download_attempt", default=None)


def _enter_stage(stage: str) -> str:
    context = _CURRENT_ATTEMPT.get()
    if context is not None:
        context.update(stage=stage, stage_started=time.monotonic())
    return stage

class Selectors:
    accept_cookies_button = "#onetrust-accept-btn-handler"
    product_select = "#_yieldchartportlet_WAR_nnportlet_selectedProduct"
    product_label = ".product-selector .cs-placeholder"
    product_option = f'.product-selector .cs-options li[data-value="{PRODUCT_VALUE}"]'
    application_error = "#_yieldchartportlet_WAR_nnportlet_errorMessage"
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
    options.page_load_strategy = "eager"
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
    try:
        driver.command_executor.client_config.timeout = COMMAND_TIMEOUT_SECONDS
        driver.set_page_load_timeout(NAVIGATION_TIMEOUT_SECONDS)
        driver.set_script_timeout(DEFAULT_TIMEOUT_SECONDS)
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)},
        )
    except Exception:
        _close_driver(driver)
        raise
    return driver


def _close_driver(driver: WebDriver) -> None:
    """Cleanup must not replace a failed attempt or discard a completed file."""
    try:
        driver.quit()
    except Exception as error:
        logger.opt(colors=False).warning("Browser cleanup failed: {}", error)


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
    # The visible widget updates its label and initiates the fund request. Never
    # replay its activation from a readiness predicate or call its handler twice.
    before = _read_yield_page_state(driver)
    try:
        _click_control(driver, Selectors.product_label)
        _click_control(driver, Selectors.product_option)
        _wait_for_state(driver, "product activation", _product_is_ready)
    except Exception as exception:
        exception.product_state_before = before
        raise


def _product_is_ready(state: dict) -> bool:
    if state.get("applicationError"):
        error = RuntimeError(
            f"NN product activation failed for {PRODUCT_NAME} ({PRODUCT_VALUE}): "
            f"{state['applicationError']}"
        )
        error.last_yield_state = state
        raise error
    return (
        state.get("productValue") == PRODUCT_VALUE
        and state.get("productText") == PRODUCT_NAME
        and state.get("productLabel") == PRODUCT_NAME
        and state.get("productLabelVisible")
        and state.get("fundGroupVisible")
        and state.get("fundCount", 0) > 0
        and not state.get("loading")
    )


def _dismiss_cookie_banner(driver: WebDriver) -> None:
    _click_if_visible(driver, Selectors.accept_cookies_button, timeout=0)


def _click_control(driver: WebDriver, selector: str) -> None:
    def clickable(active_driver):
        _dismiss_cookie_banner(active_driver)
        return EC.element_to_be_clickable((By.CSS_SELECTOR, selector))(active_driver)

    WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(clickable).click()


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
    state = driver.execute_script(
        """
        const product = document.querySelector(arguments[0]);
        const fromDate = document.querySelector(arguments[1]);
        const toDate = document.querySelector(arguments[2]);
        const table = document.querySelector(arguments[3]);
        const downloadContainer = document.querySelector(arguments[4]);
        const downloadButton = document.querySelector(arguments[5]);
        const productLabel = document.querySelector(arguments[6]);
        const funds = Array.from(document.querySelectorAll(arguments[7]));
        const error = document.querySelector(arguments[8]);
        const fundGroup = document.querySelector(arguments[9]);

        const visible = element => {
            if (!element) return false;
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' &&
                rect.width > 0 && rect.height > 0;
        };

        return {
            documentReadyState: document.readyState,
            requiredFunctions: {
                productOnChange: typeof window._yieldchartportlet_WAR_nnportlet_productOnChange === 'function',
                toggleButtonAndLabelState: typeof window._yieldchartportlet_WAR_nnportlet_toggleButtonAndLabelState === 'function',
            },
            productControlPresent: Boolean(product),
            dateControlsPresent: Boolean(fromDate && toDate),
            productLabelVisible: visible(productLabel),
            productLabel: productLabel ? productLabel.textContent.trim() : null,
            fundCount: funds.length,
            fundIds: funds.map(item => item.value),
            fundGroupVisible: visible(fundGroup),
            applicationError: visible(error) ? error.textContent.trim() : '',
            loading: fundGroup && fundGroup.hasAttribute('aria-busy')
                ? fundGroup.getAttribute('aria-busy') === 'true' : null,
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
        Selectors.product_label,
        Selectors.asset_fund_checkboxes,
        Selectors.application_error,
        Selectors.asset_funds_checkbox_group,
    )
    context = _CURRENT_ATTEMPT.get()
    if context is not None:
        context["last_state"] = state
    return state


def _wait_for_state(driver: WebDriver, stage: str, predicate) -> dict:
    """Poll observations without repeating the action that initiated a change."""
    last_state = None

    def ready(active_driver):
        nonlocal last_state
        last_state = _read_yield_page_state(active_driver)
        return last_state if predicate(last_state) else False

    try:
        return WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until(ready)
    except TimeoutException as exc:
        error = RuntimeError(f"NN {stage} did not become ready: {last_state}")
        error.download_stage = stage
        error.last_yield_state = last_state
        raise error from exc


def _wait_for_application_ready(driver: WebDriver) -> dict:
    return _wait_for_state(
        driver, "application readiness",
        lambda state: all(state.get("requiredFunctions", {}).get(name) for name in (
            "productOnChange", "toggleButtonAndLabelState",
        )) and state.get("productControlPresent") and state.get("dateControlsPresent")
        and state.get("productLabelVisible"),
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
        return _product_is_ready(last_state) and all(
            last_state.get(key) == value for key, value in expected.items()
        )

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
            _dismiss_cookie_banner(active_driver)
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
            _dismiss_cookie_banner(active_driver)
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
    """Failure-only evidence; readiness collection cannot replace cached state.

    Added metadata: stage, elapsed_seconds, stage_elapsed_seconds,
    last_observed_state, product_state_before and best-effort readiness.
    Individual browser evidence failures remain in collection_errors.
    """
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
        "product_name": PRODUCT_NAME,
        "product_value": PRODUCT_VALUE,
        # Session capabilities contain startup defaults, not subsequent timeout
        # changes. Record our effective budgets separately to avoid ambiguity.
        "timeout_budgets_seconds": {
            "navigation": NAVIGATION_TIMEOUT_SECONDS,
            "application": DEFAULT_TIMEOUT_SECONDS,
            "script": DEFAULT_TIMEOUT_SECONDS,
            "download": DOWNLOAD_TIMEOUT_SECONDS,
            "connection": COMMAND_TIMEOUT_SECONDS,
        },
        "stage": getattr(exception, "download_stage", None),
        "elapsed_seconds": getattr(exception, "elapsed_seconds", None),
        "stage_elapsed_seconds": getattr(exception, "stage_elapsed_seconds", None),
        "last_observed_state": getattr(exception, "last_yield_state", None),
        "product_state_before": getattr(exception, "product_state_before", None),
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
    collect("readiness", lambda: _read_yield_page_state(driver))
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
    Stages: navigation -> application readiness -> product activation -> date
    confirmation -> fund selection -> form submission -> table readiness -> file
    download. Input assignment alone does not establish application readiness.
    """

    resolved_start_date, resolved_end_date = _resolve_dates(start_date, end_date)
    start_parts = _to_hungarian_date_parts(resolved_start_date)
    end_parts = _to_hungarian_date_parts(resolved_end_date)
    
    with tempfile.TemporaryDirectory(prefix="nn-euro-hozam-") as tmpdir:
        download_dir = Path(tmpdir)
        driver = _build_driver(download_dir)

        started = time.monotonic()
        context = {"started": started, "last_state": None}
        token = _CURRENT_ATTEMPT.set(context)
        stage = _enter_stage("navigation")
        try:
            driver.get(TARGET_URL)
            stage = _enter_stage("application readiness")
            _wait_for_application_ready(driver)
            _click_if_visible(driver, Selectors.accept_cookies_button)
            _wait_for_css(driver, Selectors.product_select)

            stage = _enter_stage("product activation")
            _select_product(driver)
            stage = _enter_stage("date confirmation")
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

            stage = _enter_stage("fund selection")
            _select_all_asset_funds(driver)
            stage = _enter_stage("form submission")
            _submit_yield_form(driver, start_parts, end_parts)

            stage = _enter_stage("table readiness")
            _click_control(driver, Selectors.table_view_button)
            _wait_for_table_download_ready(driver, start_parts, end_parts)
            _click_table_download(driver, start_parts, end_parts)

            stage = _enter_stage("file download")
            downloaded_file = _wait_for_download(download_dir)
            if downloaded_file.stat().st_size <= 0:
                raise RuntimeError(f"Downloaded file is empty: {downloaded_file}")
        except Exception as exception:
            exception.download_stage = stage
            exception.elapsed_seconds = time.monotonic() - started
            exception.stage_elapsed_seconds = time.monotonic() - context["stage_started"]
            exception.last_yield_state = getattr(exception, "last_yield_state", None) or context["last_state"]
            exception.add_note(
                f"{stage} failed for {PRODUCT_NAME} ({PRODUCT_VALUE}), "
                f"{resolved_start_date} to {resolved_end_date}"
            )
            try:
                diagnostic_bundle = _capture_failure_diagnostics(
                    driver,
                    exception,
                    resolved_start_date,
                    resolved_end_date,
                    attempt_number,
                )
            except Exception as capture_error:
                diagnostic_bundle = None
                logger.opt(colors=False).error("Failure evidence collection failed: {}", capture_error)
                exception.add_note(f"Failure evidence collection failed: {capture_error}")
            if diagnostic_bundle is not None:
                exception.add_note(f"Selenium diagnostics saved to {diagnostic_bundle}")
            raise
        finally:
            _CURRENT_ATTEMPT.reset(token)
            _close_driver(driver)

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


def _batch_intervals(start_date, end_date, interval, retries, min_sleep_secs):
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 1:
        raise ValueError("retries must be a positive total attempt count")
    if (not isinstance(min_sleep_secs, (int, float)) or
            not math.isfinite(min_sleep_secs) or min_sleep_secs < 0):
        raise ValueError("min_sleep_secs must be finite and nonnegative")
    if interval not in ("daily", "weekly"):
        raise ValueError("interval must be daily or weekly")
    start, end = _resolve_dates(start_date, end_date)
    if start >= end or end > date.today():
        raise ValueError("Batch dates must be increasing and end no later than today")
    step = timedelta(days=1 if interval == "daily" else 7)
    intervals = []
    while start < end:
        next_end = min(start + step, end)
        intervals.append((start, next_end))
        start = next_end
    return intervals


def _range(start, end):
    return {"start": start.isoformat(), "end": end.isoformat()}


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
    stop_event: Event | None = None,
):
    """Download a contiguous batch, stopping at the first exhausted interval.

    ``retries`` is the TOTAL attempt budget per interval, including the first.
    Zero sleep is supported. Cancellation interrupts waits and is checked before
    each attempt; an in-flight browser command must finish or time out. A final
    successful interval completes the batch even if cancellation arrived during
    that attempt. Ordinary completion never sets the caller's cancellation event.

    Return a dict with status (completed/failed/cancelled), requested_start/end,
    total_intervals, completed_intervals, files (list[Path]), completed_ranges
    (requested interval start/end dictionaries), completed_range, uncovered_range,
    failed_interval, attempt_count (last attempted interval), total_attempts,
    error, stage and diagnostic_bundle. Coverage describes successful requested
    intervals, not a guarantee that each calendar date has a published NAV.

    Queue protocol (producer and consumer must be upgraded together):
    * progress_queue receives integer percentages, then exactly one dictionary
      ``{"type": "finished", "status": "failed", ...}`` containing the return
      fields, with files serialized as strings. There is no "done" sentinel.
    * result_queue receives one list[Path], only if files exist, BEFORE the
      terminal event. Failed/cancelled partial files remain available for merge.
      Neither queue causes automatic merging. Invalid inputs still publish a
      failed outcome with initialized empty results and zero completed intervals.
    """
    stop_event = stop_event if stop_event is not None else Event()
    downloaded_files = []
    intervals = []
    outcome = {
        "status": "failed", "requested_start": str(start_date), "requested_end": str(end_date),
        "total_intervals": 0, "completed_intervals": 0, "completed_ranges": [],
        "completed_range": None, "uncovered_range": None, "failed_interval": None,
        "attempt_count": 0, "total_attempts": 0, "error": None, "stage": "validation",
        "diagnostic_bundle": None, "files": downloaded_files,
    }
    try:
        intervals = _batch_intervals(start_date, end_date, interval, retries, min_sleep_secs)
        outcome.update(total_intervals=len(intervals), requested_start=intervals[0][0].isoformat(),
                       requested_end=intervals[-1][1].isoformat())
        destination = Path(outfile_path).resolve() if outfile_path else Path.cwd()
        outcome["stage"] = "batch execution"
        for index, (start, end) in enumerate(intervals):
            if stop_event.is_set() or (index > 0 and stop_event.wait(min_sleep_secs)):
                outcome["status"] = "cancelled"
                return outcome
            for attempt in range(1, retries + 1):
                if stop_event.is_set():
                    outcome["status"] = "cancelled"
                    return outcome
                outcome.update(attempt_count=attempt, total_attempts=outcome["total_attempts"] + 1)
                try:
                    logger.opt(colors=False).info("Download {} to {}, attempt {}/{}", start, end, attempt, retries)
                    output = download_xls(
                        start_date=start.isoformat(), end_date=end.isoformat(),
                        outfile_path=destination, append_timestamp=append_timestamp,
                        attempt_number=attempt,
                    )
                except Exception as error:
                    bundle = next((note.removeprefix("Selenium diagnostics saved to ")
                                   for note in getattr(error, "__notes__", [])
                                   if note.startswith("Selenium diagnostics saved to ")), None)
                    outcome.update(error=str(error), stage=getattr(error, "download_stage", "download"),
                                   diagnostic_bundle=bundle)
                    logger.opt(colors=False).error("Download {} to {} failed: {}", start, end, error)
                    if bundle:
                        logger.opt(colors=False).error("Selenium diagnostics saved to {}", bundle)
                    if stop_event.is_set():
                        outcome["status"] = "cancelled"
                        return outcome
                    if attempt == retries:
                        outcome["failed_interval"] = _range(start, end)
                        return outcome
                    delay = min_sleep_secs + randint(0, int(min_sleep_secs))
                    if stop_event.wait(delay):
                        outcome["status"] = "cancelled"
                        return outcome
                else:
                    downloaded_files.append(output)
                    outcome["completed_ranges"].append(_range(start, end))
                    outcome.update(completed_intervals=index + 1, error=None, stage=None, diagnostic_bundle=None)
                    if progress_queue is not None and not progress_queue.full():
                        progress_queue.put(int((index + 1) / len(intervals) * 100))
                    break
        outcome["status"] = "completed"
    except Exception as error:
        outcome.update(status="failed", error=str(error), stage=outcome.get("stage") or "batch execution")
        if intervals and outcome["completed_intervals"] < len(intervals):
            start, end = intervals[outcome["completed_intervals"]]
            outcome["failed_interval"] = _range(start, end)
        logger.opt(colors=False).error("Download batch failed: {}", error)
    finally:
        count = outcome["completed_intervals"]
        if count:
            outcome["completed_range"] = _range(intervals[0][0], intervals[count - 1][1])
        if intervals and count < len(intervals):
            outcome["uncovered_range"] = _range(intervals[count][0], intervals[-1][1])
        if result_queue is not None and downloaded_files:
            result_queue.put(list(downloaded_files))
        if progress_queue is not None:
            progress_queue.put({"type": "finished", **outcome, "files": [str(path) for path in downloaded_files]})
    return outcome


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
        help="Total number of attempts per interval, including the first attempt.",
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
