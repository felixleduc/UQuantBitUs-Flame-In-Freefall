# NASA Space Apps 2026: combustion dashboard

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                 # create .venv and install the packages
uv run playwright install chromium      # once, browser used to read the PSI pages
```

No data is stored in this repository. `data/files.csv` lists every file the PSI combustion
investigations hold (66,459), with two columns to triage them: `useful` (yes or no, for the
dashboard) and `content` (what the file is). The useful ones are downloaded on demand:

```bash
uv run python src/download_psi_files.py              # the useful files: about 2,900 files, 1.5 GB
uv run python src/download_psi_files.py 25 99        # only those of PSI-25 and PSI-99
uv run python src/download_psi_files.py --all        # every document, useful or not: 25,000 files, 11 GB
uv run python src/download_psi_files.py --workers 4  # fewer browsers at once (default 8), for less memory
uv run python src/list_psi_files.py                  # rebuild data/files.csv (takes hours)
```

The download runs 8 browsers side by side and can be interrupted and rerun: files already on
disk are skipped. To split it between several machines, each one adds `--part 1/3`, `--part 2/3`,
`--part 3/3`.

Files land in `data/raw/PSI-<id>_<name>/`, in the folders PSI uses. Videos, images and camera
data are never downloaded. The rules behind `useful` are the `USEFUL` list in `src/list_psi_files.py`.
