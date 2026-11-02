# nn-euro-hozam
NN Euro-based savings and investment yield scraper and visualizer using Streamlit with Plotly.

![alt text](./data/screenshots/screenshot1.png?raw=true "Settings")

![alt text](./data/screenshots/screenshot2.png?raw=true "Asset Yields")

## Downloader outcomes

- **Download complete!** means every requested interval was downloaded; progress is 100%.
- **Download failed. The batch stopped.** means an interval exhausted its attempt budget or a worker error occurred. Later intervals are not attempted. The page shows completed coverage, the failed interval where applicable, the uncovered range, and available error/diagnostic details.
- **Download cancelled.** preserves completed files and actual progress. Cancel interrupts waits and prevents new attempts; an in-flight browser command must finish or time out first.
- **Merge partial results** explicitly imports only the successfully downloaded files from a failed or cancelled batch. Check the displayed coverage first: this does not complete the original requested range. A complete batch uses **Merge**. Neither action runs automatically, and no merge is offered when no files were downloaded.

The `retries` argument is the **total attempts per interval**, including the first attempt. Downloads check NN application readiness and product activation before submitting the form. Failure-only diagnostic bundles are stored in `nn_euro_hozam/data/debug/`, with the ten newest retained.

**Restart Streamlit after upgrading this downloader.** Its worker and page now use a structured terminal outcome instead of the old `"done"` queue message; both must run the matching version. Run state is held in the current Streamlit session, so finish or cancel an active run before restarting.

Regression checks:

```bash
PYTHONPATH=nn_euro_hozam:. python -B -m unittest discover -s tests -v
```
