# NASA Space Apps 2026: combustion dashboard

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                 # create .venv and install the packages
uv run playwright install chromium      # once, browser used to read the PSI pages
```

No data is stored in this repository. `data/files.csv` lists every file the PSI
combustion investigations hold; the documents among them are downloaded on demand:

```bash
uv run python src/download_psi_files.py              # all documents of all investigations
uv run python src/download_psi_files.py 25 99        # only those of PSI-25 and PSI-99
uv run python src/download_psi_files.py --workers 4  # fewer browsers at once (default 8), for less memory
uv run python src/list_psi_files.py                  # rebuild data/files.csv (takes hours)
```

The download runs 8 browsers side by side. A full run is about 23,000 files (9 GB) and takes
a few hours. It can be interrupted and rerun: files already on disk are skipped. To split it
between several machines, each one adds `--part 1/3`, `--part 2/3`, `--part 3/3`.

Files land in `data/raw/PSI-<id>_<name>/`, in the folders PSI uses. Only PDF, Word, Excel, PowerPoint, CSV and text files are downloaded: no videos, images or camera data.
