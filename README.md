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

Three CSV files, comma separated, UTF-8, one header line. Empty cell = not known.

| File | Rows | One row per | Key |
|---|---|---|---|
| `tests.csv` | 3,821 | test (one ignition attempt, droplet, burn or smoke run) | `psi_id` + `test_id` |
| `investigations.csv` | 19 | PSI investigation | `psi_id` |
| `context.csv` | 941 | fact read in a report, paper or crew note | none (`psi_id` + `test_id` + `field`) |

`tests.csv` joins `investigations.csv` on `psi_id`. The `context.csv` rows that have a `test_id`
are already merged into `tests.csv`.

### `tests.csv`

The same 38 columns for every investigation. A column only some investigations measured is empty
for the others, so filter on `fuel_type` (or `investigation`) before modelling.

| `fuel_type` | Tests | Investigations |
|---|---|---|
| `gas jet` | 1,784 | CFI-G, Flame-Design, SPICE, CLD-Flame, E-FIELD-Flames, SLICE |
| `droplet` | 1,080 | FLEX, CFI, FLEX-2 |
| `gas burner` | 514 | BRE, s-Flame |
| `solid` | 263 | BASS, BASS-II, SAFFIRE-I, SAFFIRE-II, SAFFIRE-III |
| `smoke` | 174 | SAME, SAME-R (heated samples, no flame) |
| `aerosol` | 6 | DAFT (test dust and cabin air) |

Columns (unit, share of rows filled):

| Column | Meaning |
|---|---|
| `psi_id` | Investigation, `PSI-<number>` (100 %) |
| `investigation` | Short name, e.g. `BASS-II` (100 %) |
| `test_id` | Test name used by NASA (`M12`, `21328A1`, `1206`...); a `b` suffix marks a second test NASA numbered the same (100 %) |
| `date` | `YYYY-MM-DD`, or mission day as written (`day 3`, `GMT day 45`) when no calendar date exists (100 %) |
| `fuel_type` | See table above (100 %) |
| `material` | Sample or fuel as NASA wrote it (88 %) |
| `material_family` | Normalised material: `PMMA`, `SIBAL cotton-fiberglass fabric`, `Nomex`, `silicone`, `C2H4`, `CH4`, `Heptane`... (88 %) |
| `geometry` | `sphere`, `rod`, `slab`, `thin sheet`, `flat sheet`, `fabric`, `candle`, `droplet`, `coflow jet flame`, `normal spherical flame`, `inverse spherical flame`, `spherical burner flame`, `porous burner (BRE)`... (95 %) |
| `thickness_mm` | Solid sample thickness, mm (1 %) |
| `width_cm`, `length_cm` | Solid sample width and length, cm (3 %, under 1 %) |
| `diameter_mm` | Sphere or rod diameter, initial droplet diameter, or nozzle diameter, mm (32 %) |
| `o2_percent` | O2 around the flame at the start, % by volume. Inverse flames: O2 of the burner jet (91 %) |
| `co2_percent` | CO2 at the start, % by volume (45 %) |
| `pressure_atm` | Chamber or cabin pressure, atm (70 %) |
| `diluent` | Inert gas: `N2`, `He`, `N2+CO2`, `N2+He` (63 %) |
| `flow_cm_s` | Air flow speed at ignition, cm/s (37 %) |
| `flow_steps_cm_s` | Successive flow settings during the test, text such as `10 > 5 > 2` (8 %) |
| `flow_direction` | `concurrent` (flow along the spread) or `opposed` (flow against it) (30 %) |
| `ignited` | `yes` / `no` (79 %) |
| `outcome` | How the test ended, see below (72 %) |
| `burn_time_s` | Flame duration, s (60 %) |
| `spread_rate_mm_s` | Flame spread rate over a solid, mm/s (1 %) |
| `o2_final_percent` | O2 at the end of the test, % (3 %, solids) |
| `extinction_diameter_mm` | Droplet diameter when the flame went out, mm (9 %, FLEX, CFI) |
| `burning_rate_mm2_s` | Droplet burning rate K, mm2/s (11 %, FLEX, CFI) |
| `cool_flame` | `yes` / `probable` / `no`: a low-temperature flame followed extinction (6 %, droplets, CFI-G) |
| `lifted` | `yes` when the flame detached from the burner (2 %, SPICE) |
| `peak_heat_flux_kw_m2` | Peak radiometer rise after the igniter, kW/m2 (Saffire) |
| `peak_sample_temp_c` | Peak thermocouple temperature in the sample, C (Saffire) |
| `fuel_percent` | Fuel share of the fuel stream, % (14 %, CLD-Flame, E-FIELD-Flames) |
| `flame_length_mm` | Luminous flame length, mm (4 %, SPICE) |
| `smoke_point_length_mm` | Flame length when it starts to release soot, mm (1 %, SPICE) |
| `smoke_mean_diameter_um` | Count mean smoke particle diameter, micrometres (3 %, SAME, SAME-R) |
| `smoke_number_per_cm3` | Smoke particle number concentration, per cm3 (3 %) |
| `smoke_mass_mg_m3` | Smoke mass concentration, mg/m3 (4 %) |
| `notes` | Everything else NASA or the crew wrote for the test, as text (99 %) |
| `source` | File(s) the row was read from, relative to the repository (100 %) |

Main `outcome` values: `flow terminated` (780, the flow was cut on schedule while the flame still
burned), `self-extinguished` (631), `no ignition` (349), `extinction, then cool flame` (170),
`extinction` (126), `extinguished at low flow` (110, the flame went out when the air flow was
reduced), `brief flame` (87, ignited but did not spread), `lifted flame` (67), `smoke point reached`
(63), `disruption` (61, the droplet broke apart), `burned out` (47, the sample was consumed),
`burned` (45, burned, end not stated), `radiative` / `diffusive extinction`, `blown off` (16),
`extinguished by N2` (2), `not run (...)` (aborted before a real attempt: drop these rows when
modelling). SLICE rows (one per day) have free-text outcomes.

Read before analysing:
- `burn_time_s` for ACME flames (CFI-G, Flame-Design, BRE, CLD-Flame, E-FIELD-Flames, s-Flame)
  includes a few seconds of igniter time; when `outcome` is `flow terminated` it is the planned
  test length, not a natural burn.
- Missing because NASA did not record it per test: FLEX-2 outcomes, pressure for BASS-II,
  E-FIELD-Flames and SPICE (both near 1 atm, cabin), part of the SPICE outcomes.
- Values NASA got wrong were corrected or blanked (swapped Saffire-I dimensions, BASS-II year 2018,
  impossible final O2); each correction is commented in `src/unify_data.py` or quoted in
  `context.csv`.

### `investigations.csv`

From each investigation's metadata archive. Columns: `psi_id`, `acronym`, `title`, `group`
(`solid materials`, `fuel and flame physics`, `smoke detection`, `flame structure`), `tests` (rows in
`tests.csv`), `platform`, `hardware`, `nasa_center`, `start_date`, `end_date`,
`principal_investigator`, `topics`, `objective`, `hypothesis`, `approach`, `research_impacts`,
`doi`, `publications` (count), `url` (PSI page).

### `context.csv`

Facts read in prose, each traceable to its source. Columns: `psi_id`, `test_id`, `field`, `value`,
`quote` (exact sentence or table line, spaces collapsed), `file` (relative path in `data/raw/`),
`page` (PDF page number, or sheet and row for spreadsheets).

- 785 rows with a `test_id`: `field` is a column of `tests.csv` and `value` fills or corrects that
  cell (outcomes from crew notes, BASS-II report tables, daily notes).
- 156 rows without `test_id`: findings for the whole investigation, to show in the dashboard.
  `field` is `finding`, `detection`, `smoke`, `smoke_size`, `material_flammability`,
  `min_o2_percent`, `ignition_limit_o2_percent`, `extinction_flow_cm_s`, `suppression`, `cool_flame`...;
  `value` starts with the number when there is one, e.g. `17.5 (PMMA rods, opposed-flow spread,
  microgravity; 19 in normal gravity)`.

### Loading with pandas and scikit-learn

```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

tests = pd.read_csv("data/processed/tests.csv", low_memory=False)
tests = tests[~tests.outcome.fillna("").str.startswith(("not run", "aborted"))]

# Would this solid ignite? (246 tests, 90 % ignited: use a balanced score)
solids = tests[(tests.fuel_type == "solid") & tests.ignited.isin(["yes", "no"])]
X = pd.get_dummies(
    solids[["material_family", "geometry", "o2_percent", "flow_cm_s", "thickness_mm", "diameter_mm"]],
    columns=["material_family", "geometry"],
).fillna(-1)
y = solids.ignited == "yes"
print(cross_val_score(RandomForestClassifier(random_state=0), X, y, cv=5, scoring="balanced_accuracy").mean())

# Findings for the dashboard text
context = pd.read_csv("data/processed/context.csv")
findings = context[context.test_id.isna()]
```

Other datasets that fit a model: gas flames (`fuel_type` in `gas jet`, `gas burner`, about 2,300
tests) to predict `outcome` from `o2_percent`, `pressure_atm`, `fuel_percent`, `material_family`;
droplets (FLEX and CFI, about 500 tests) to predict `burning_rate_mm2_s` or `extinction_diameter_mm`
from `o2_percent`, `pressure_atm`, `diluent`, `diameter_mm`.

### Rebuilding the tables

```bash
uv run python src/unify_data.py   # about 1 minute; needs data/raw/ and pdftotext (poppler-utils)
```

Values come, in order of priority: experimental tables, then the per-test files read by
`src/readers/` (one module per group of investigations), then `context.csv`. To fix a value by
hand, add a row to `context.csv` with its quote and source, then rebuild.

## Dashboard (`dashboard/`)

Next.js app that reads `dashboard/data/*.json`. To refresh them after `data/processed/` changes:

```bash
uv run python src/export_dashboard_data.py   # tests.json and findings.json
uv run python ML.py                          # model.json: trains the model and prints its scores
```

`ML.py` trains a logistic regression on the 218 solid-material flight tests with a known
outcome, oxygen and air flow: will a flame keep burning, from material, sample shape, oxygen and
flow. Cross-validated ROC AUC 0.84 (0.5 is chance). Pressure is not an input because every solid
was flown near 1 atm. See `dashboard/README.md` to run the site.
