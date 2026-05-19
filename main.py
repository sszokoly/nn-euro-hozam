import sys
from selenium.common.exceptions import TimeoutException
from nn_euro_yields import download_yields


def main():
    try:
        path = download_yields(append_timestamp=True)
    except (TimeoutError, TimeoutException) as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    print(path)


if __name__ == "__main__":
    main()
