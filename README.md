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

## Unified tables (`data/processed/`, committed)

- `investigations.csv`: one row per PSI investigation (objective, hypothesis, dates, PI, topics).
- `tests.csv`: one row per test with the same columns everywhere (material, geometry, size, O2,
  pressure, flow, outcome...), joined to the above on `psi_id`. Measurement columns that only some
  investigations have: final O2 and peak heat flux and sample temperature (solids), extinction
  diameter, burning rate and cool flame (droplets), flame and smoke point length, lifted flame and
  fuel percent (gas flames), smoke particle diameter, number and mass (smoke detection).
- `context.csv`: facts read in reports and crew notes, each with its exact quote, file and PDF page.
  Rows with a `test_id` fill or correct that test in `tests.csv`; the others are findings for the
  whole investigation (oxygen limits, extinction flows).

`tests.csv` and `investigations.csv` are rebuilt from `data/raw/` and `context.csv` with
(about 1 minute; needs `pdftotext` from poppler-utils):

```bash
uv run python src/unify_data.py
```

Values come, in order of priority: experimental tables, then the per-test files read by
`src/readers/` (one module per group of investigations), then `context.csv`.

Read before analysing:
- `burn_time_s` for ACME flames includes a few seconds of igniter time; when `outcome` is
  "flow terminated" it is the planned test length, not a natural burn.
- `o2_percent` is the O2 around the flame, except for inverse flames (Flame Design, CFI-G) where
  it is the O2 of the burner jet.
- FLEX-2 tests have conditions but no outcome; BASS-II has no pressure; SAME, SAME-R and DAFT are
  smoke tests (heated samples, no flame).
