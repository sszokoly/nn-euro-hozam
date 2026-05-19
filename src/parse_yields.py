from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import xlrd
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from xlrd.xldate import XLDateError


HEADER_ROW_INDEX = 1
DATA_START_ROW_INDEX = 2

FIELD_NAMES = (
    "asset_name",
    "opening_date",
    "opening_value",
    "closing_date",
    "closing_value",
    "period_yield",
)

HEADER_MAP = {
    "Eszközalap": "asset_name",
    "Eszközalap neve": "asset_name",
    "Kezdő árfolyam": "opening_value",
    "Kezdő dátum": "opening_date",
    "Záró árfolyam": "closing_value",
    "Záró dátum": "closing_date",
    "Hozam": "period_yield",
}


@dataclass(frozen=True)
class CellValue:
    value: Any
    is_percent_format: bool = False


class YieldRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    asset_name: str | None = None
    opening_date: str | None = None
    opening_value: float | None = None
    closing_date: str | None = None
    closing_value: float | None = None
    period_yield: float | None = None

    @field_validator("asset_name", mode="before")
    @classmethod
    def _validate_asset_name(cls, value: Any) -> str | None:
        return _coerce_text(value)

    @field_validator("opening_date", "closing_date", mode="before")
    @classmethod
    def _validate_date(cls, value: Any) -> str | None:
        return _coerce_date(value)

    @field_validator("opening_value", "closing_value", mode="before")
    @classmethod
    def _validate_float(cls, value: Any) -> float | None:
        return _coerce_float(value)

    @field_validator("period_yield", mode="before")
    @classmethod
    def _validate_period_yield(cls, value: Any) -> float | None:
        return _coerce_period_yield(value)


def _unwrap_cell(value: Any) -> Any:
    if isinstance(value, CellValue):
        return value.value

    return value


def _coerce_text(value: Any) -> str | None:
    raw_value = _unwrap_cell(value)
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    return text or None


def _coerce_date(value: Any) -> str | None:
    raw_value = _unwrap_cell(value)
    if raw_value is None:
        return None

    if isinstance(raw_value, datetime):
        return raw_value.date().isoformat()

    if isinstance(raw_value, date):
        return raw_value.isoformat()

    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return None

        hungarian_match = re.fullmatch(
            r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?",
            text,
        )
        if hungarian_match:
            year, month, day = (int(part) for part in hungarian_match.groups())
            return date(year, month, day).isoformat()

        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            pass

        try:
            return datetime.fromisoformat(text).date().isoformat()
        except ValueError as exc:
            raise ValueError("invalid date") from exc

    raise ValueError("invalid date")


def _coerce_float(value: Any) -> float | None:
    raw_value = _unwrap_cell(value)
    if raw_value is None:
        return None

    if isinstance(raw_value, str) and not raw_value.strip():
        return None

    if isinstance(raw_value, bool):
        raise ValueError("invalid number")

    if isinstance(raw_value, int | float):
        return _ensure_finite(float(raw_value))

    if isinstance(raw_value, str):
        return _ensure_finite(_parse_number(raw_value))

    raise ValueError("invalid number")


def _coerce_period_yield(value: Any) -> float | None:
    cell = value if isinstance(value, CellValue) else CellValue(value)
    raw_value = cell.value

    if raw_value is None:
        return None


    if isinstance(raw_value, str) and not raw_value.strip():
        return None

    if isinstance(raw_value, bool):
        raise ValueError("invalid percentage")

    if isinstance(raw_value, int | float):
        number = _ensure_finite(float(raw_value))
        if cell.is_percent_format:
            return number
        return number / 100

    if isinstance(raw_value, str):
        return _ensure_finite(_parse_number(raw_value) / 100)

    raise ValueError("invalid percentage")


def _ensure_finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("number must be finite")

    return value


def _parse_number(value: str) -> float:
    text = value.strip().replace("\xa0", " ").replace("−", "-")
    for token in ("EUR", "Eur", "eur", "€", "%"):
        text = text.replace(token, "")
    text = re.sub(r"\s+", "", text)

    if not text:
        raise ValueError("empty number")

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    return float(text)


def _normalize_header(value: Any) -> str:
    raw_value = _unwrap_cell(value)
    if raw_value is None:
        return ""

    return " ".join(str(raw_value).strip().split())


def _is_percent_cell(workbook: xlrd.book.Book, cell: xlrd.sheet.Cell) -> bool:
    try:
        xf = workbook.xf_list[cell.xf_index]
        cell_format = workbook.format_map[xf.format_key]
    except (AttributeError, IndexError, KeyError):
        return False

    return "%" in cell_format.format_str


def _read_cell(
    workbook: xlrd.book.Book,
    sheet: xlrd.sheet.Sheet,
    row_index: int,
    column_index: int,
) -> CellValue:
    cell = sheet.cell(row_index, column_index)
    value = cell.value

    if cell.ctype in {xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR}:
        value = None
    elif cell.ctype == xlrd.XL_CELL_DATE:
        try:
            value = xlrd.xldate_as_datetime(value, workbook.datemode)
        except (ValueError, OverflowError, XLDateError):
            pass

    return CellValue(
        value=value,
        is_percent_format=_is_percent_cell(workbook, cell),
    )


def _header_indexes(
    workbook: xlrd.book.Book,
    sheet: xlrd.sheet.Sheet,
) -> dict[str, int]:
    if sheet.nrows <= HEADER_ROW_INDEX:
        return {}

    indexes: dict[str, int] = {}
    for column_index in range(1, sheet.ncols):
        header = _normalize_header(
            _read_cell(workbook, sheet, HEADER_ROW_INDEX, column_index)
        )
        field_name = HEADER_MAP.get(header)
        if field_name is not None:
            indexes[field_name] = column_index

    return indexes


def _is_empty_value(value: Any) -> bool:
    raw_value = _unwrap_cell(value)
    if raw_value is None:
        return True

    if isinstance(raw_value, str):
        return not raw_value.strip()

    return False


def _is_empty_row(row: dict[str, CellValue]) -> bool:
    return all(_is_empty_value(value) for value in row.values())


def _round_float_values(
    row: dict[str, str | float | None],
    round_digits: int | None,
) -> dict[str, str | float | None]:
    if round_digits is None:
        return row

    return {
        key: round(value, round_digits) if isinstance(value, float) else value
        for key, value in row.items()
    }


def _coerce_row(
    row: dict[str, CellValue],
    round_digits: int | None,
) -> dict[str, str | float | None]:
    candidate: dict[str, Any] = {field_name: row.get(field_name) for field_name in FIELD_NAMES}

    for _ in range(len(FIELD_NAMES) + 1):
        try:
            validated_row = YieldRow.model_validate(candidate).model_dump()
            return _round_float_values(validated_row, round_digits)
        except ValidationError as exc:
            failed_fields = {
                str(error["loc"][0])
                for error in exc.errors()
                if error.get("loc") and str(error["loc"][0]) in FIELD_NAMES
            }
            if not failed_fields:
                raise

            for field_name in failed_fields:
                candidate[field_name] = CellValue(None)

    raise RuntimeError("Could not coerce row values")


def _load(
    path: Path,
    round_digits: int | None,
) -> dict[str, dict[str, list[dict[str, str | float | None]]]]:
    workbook = xlrd.open_workbook(path, formatting_info=True)
    data: dict[str, dict[str, list[dict[str, str | float | None]]]] = {}

    for sheet in workbook.sheets():
        indexes = _header_indexes(workbook, sheet)
        rows: list[dict[str, str | float | None]] = []

        for row_index in range(DATA_START_ROW_INDEX, sheet.nrows):
            row = {
                field_name: _read_cell(workbook, sheet, row_index, column_index)
                for field_name, column_index in indexes.items()
            }
            row.update(
                {
                    field_name: CellValue(None)
                    for field_name in FIELD_NAMES
                    if field_name not in row
                }
            )

            if _is_empty_row(row):
                break

            rows.append(_coerce_row(row, round_digits))

        data[sheet.name] = {"data": rows}

    return data


def parse_yields(
    src_dir: str | Path | None = None,
    round_digits: int | None = None,
) -> dict[str, Any]:
    if round_digits is not None and round_digits < 0:
        raise ValueError("round_digits must be non-negative")

    src_path = Path(src_dir).expanduser() if src_dir is not None else Path.cwd()
    if not src_path.is_dir():
        raise NotADirectoryError(f"Source directory does not exist: {src_path}")

    data: dict[str, Any] = {}
    for path in sorted(src_path.iterdir()):
        if path.is_file() and path.suffix.lower() == ".xls":
            data[path.name] = _load(path, round_digits)

    return data


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parses NN Euro Alap yield spreadsheets."
    )
    parser.add_argument(
        "--src-dir",
        required=False,
        help="Folder containing the source yield spreadsheets. Defaults to cwd.",
    )
    parser.add_argument(
        "--round-digits",
        type=int,
        required=False,
        default=4,
        help="Optionally round parsed float values to this many decimal places.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    data = parse_yields(src_dir=args.src_dir, round_digits=args.round_digits)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
