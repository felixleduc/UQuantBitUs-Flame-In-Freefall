# Flame in Freefall: NASA Space Apps 2026

Would this material keep burning in this habitat, and what change would stop it? A dashboard
built on the 19 combustion investigations of NASA's Physical Science Informatics (PSI) repository.

## Setup

Needs [uv](https://docs.astral.sh/uv/), and `pdftotext` (poppler-utils) to rebuild the tables.

```bash
uv sync                              # Python environment
uv run playwright install chromium   # once: browser that reads the PSI pages
```

## Pipeline

| Step | Command | Writes |
|---|---|---|
| 1. List the useful PSI files | `uv run python src/list_psi_files.py` (hours) | `data/files.csv` (committed) |
| 2. Download them | `uv run python src/download_psi_files.py` (1.9 GB, resumable, `--workers`, `--part 1/3`) | `data/raw/` (not committed) |
| 3. Merge into tables | `uv run python src/unify_data.py` | `data/processed/*.csv` |
| 4. Data for the site | `uv run python src/export_dashboard_data.py` | `dashboard/data/tests.json`, `findings.json` |
| 5. Train the model | `uv run python ML.py` | `dashboard/data/model.json`, `flight-tests.json` |

Steps 3 to 5 need step 2 on your machine. Their outputs are committed, so the site and the
tables work from a fresh clone. Run the site: see `dashboard/README.md`.

## Tables (`data/processed/`)

| File | Rows | One row per |
|---|---|---|
| `tests.csv` | 3,821 | flight test, same columns for every investigation |
| `investigations.csv` | 19 | PSI investigation (title, objective, dates, PI, URL) |
| `context.csv` | 941 | fact read in a report or crew note, with its quote, file and page |

### `tests.csv`

Key `psi_id` + `test_id`. Filter on `fuel_type` first (`solid`, `gas burner`, `gas jet`,
`droplet`, `smoke`, `aerosol`): a column only some investigations measured is empty elsewhere.

- Sample: `material`, `material_family`, `geometry`, `thickness_mm`, `width_cm`, `diameter_mm`
- Conditions: `o2_percent`, `co2_percent`, `pressure_atm`, `diluent`, `flow_cm_s`, `flow_direction`
- Result: `ignited`, `outcome`, `burn_time_s`, `spread_rate_mm_s`, plus measurements of some
  investigations (`extinction_diameter_mm`, `burning_rate_mm2_s`, `cool_flame`, `flame_length_mm`,
  `smoke_mean_diameter_um`...)
- Traceability: `notes`, `source` (file read)

Read before analysing:
- `o2_percent` of inverse flames (Flame Design, CFI-G) is the burner jet's, not the air's.
- ACME `burn_time_s` includes a few seconds of igniter time; with `outcome` `flow terminated` it
  is the planned test length.
- Not recorded per test by NASA: FLEX-2 outcomes, pressure of BASS-II, E-FIELD and SPICE.
- `context.csv` rows with a `test_id` fill or correct that test; to fix a value, add a row there
  (with quote and source) and rerun step 3.

## Model (`ML.py`)

One logistic regression on the 2,100 flight tests with a flame outcome (solids, gas burners, gas
jets, droplets): will the flame keep burning. For a solid it uses material, sample shape, oxygen,
air flow and pressure. Solids were all flown near 1 atm, so their pressure effect comes from BRE,
NASA's gas-burner emulator of a burning solid, flown at 0.54 to 1 atm. On held-out solid tests:
ROC AUC 0.81 (0.5 is chance), Brier 0.128 against 0.174 for guessing the average. Likely ranges
come from 200 refits on resampled data.
