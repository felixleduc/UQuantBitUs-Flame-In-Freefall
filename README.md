# NASA Space Apps 2026: combustion dashboard

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                 # create .venv and install the packages
uv run playwright install chromium      # once, browser used to read the PSI pages
```

No data is stored in this repository. `data/files.csv` lists every file the PSI
combustion investigations hold; the documents among them are downloaded on demand:

```bash
uv run python src/download_psi_files.py --no-raw   # documents and tables (PDF, Word, Excel, CSV, text)
uv run python src/download_psi_files.py 25 99      # same, with the "Raw Data" documents, for PSI-25 and PSI-99
uv run python src/list_psi_files.py                # rebuild data/files.csv (takes hours)
```

Files land in `data/raw/PSI-<id>_<name>/`, in the folders PSI uses. Videos and images are never downloaded.
