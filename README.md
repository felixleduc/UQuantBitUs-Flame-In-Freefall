# NASA Space Apps 2026: combustion dashboard

Needs [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                 # create .venv and install the packages
uv run playwright install chromium      # once, browser used to read the PSI pages
```

No data is stored in this repository. `data/files.csv` lists the files of the PSI combustion
investigations worth having: about 7,800 out of the 66,000 NASA holds (the rest is videos,
images, camera settings and raw instrument logs). Its `useful` column says `yes`, or `maybe`
for the few nobody has opened, and `content` says what each file is. They are downloaded on demand:

```bash
uv run python src/download_psi_files.py              # the listed files: about 7,800 files, 1.9 GB
uv run python src/download_psi_files.py 25 99        # only those of PSI-25 and PSI-99
uv run python src/download_psi_files.py --workers 4  # fewer browsers at once (default 8), for less memory
uv run python src/list_psi_files.py                  # rebuild data/files.csv from the PSI pages (takes hours)
```

The download runs 8 browsers side by side and can be interrupted and rerun: files already on
disk are skipped. To split it between several machines, each one adds `--part 1/3`, `--part 2/3`,
`--part 3/3`.

Files land in `data/raw/PSI-<id>_<name>/`, in the folders PSI uses. What is kept and what is left
out is decided by the `USEFUL` rules in `src/list_psi_files.py`.
