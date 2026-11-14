# NASA Space Apps 2026: combustion dashboard

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                 # create .venv and install the packages
uv run playwright install chromium      # once, browser used to read the PSI pages
uv run jupyter lab                      # notebooks
uv run python src/fetch_psi.py          # re-download the PSI tables into data/raw/
```

`data/catalog.csv` lists the imported PSI investigations and what each table contains.
