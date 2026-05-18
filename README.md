# nn-euro-hozam
NN Euro Alap rendszeres díjas hozamszamlalo scraper

## Selenium downloader

CLI:

```bash
uv run nn-euro-hozam --start-date 2026-05-10 --end-date 2026-05-17 --outfile-path data/hozamok.xls
```

With defaults, the date range is the last 7 days ending yesterday, and the file is saved to the current directory using the downloaded filename:

```bash
uv run nn-euro-hozam
```

Python:

```python
from nn_euro_hozam import download_yields

path = download_yields(outfile_path="data/hozamok.xls")
print(path)
```
