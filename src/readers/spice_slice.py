"""Per-test data for SPICE (PSI-107) and SLICE (PSI-106) beyond the experimental tables.

SPICE: the flight record "Spice Flight Test Data II modified.xls" (the source of NASA's experimental
table, Appendix A of the final report) gives per test point the video flame length, whether the
smoke point was reached (column "SH?"), whether the flame lifted ("LO?") and crew comments
(blew off, ran out of fuel). "SmokePointReview-0g-3.xlsx" lists the 55 smoke points retained with
their smoke point length. The record also holds the methane tests of GMT day 62, missing from
NASA's table: they become new tests.

SLICE: no per-flame data was released (only calibrations and boundary-condition scans), so the
experimental table gives one test per day of operations.

"""

import datetime as dt
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[2]

import pandas as pd

import unify_data as u

SPICE_DIR = u.folder(107) / "Raw Data" / "Reduced Gravity" / "SPICE Day 045"
RECORD = SPICE_DIR / "PSI-107_Raw Data_Spice Flight Test Data II modified.xls"
SMOKE_POINTS = SPICE_DIR / "PSI-107_Raw Data_SmokePointReview-0g-3.xlsx"


def rel(path: Path) -> str:
    return str(path.relative_to(u.ROOT))


def clock(value) -> str:
    """GMT times are written 14:37:08, 14.34.57, 08:56:16 or as Excel times: give '8:56:16'."""
    if isinstance(value, (dt.time, dt.datetime)):
        return f"{value.hour}:{value.minute:02d}:{value.second:02d}"
    s = u.text(value)
    if m := re.fullmatch(r"(\d{1,2})[:.](\d{2})[:.](\d{2})", s):
        return f"{int(m[1])}:{m[2]}:{m[3]}"
    return s.lower()


def day(value) -> int | None:
    n = u.first(u.text(value).lstrip("0") or None)
    return int(n) if n is not None else None


# ---------------------------------------------------------------- SPICE

def spice_tests() -> list[dict]:
    """tests.csv rows of SPICE, rebuilt with unify_data so test_ids match, plus their raw table values."""
    frame, _ = u.table(107)
    rows = u.unique(u.spice())
    # unique() keeps table order and drops exact duplicates: pair each kept row with its table line
    lines = iter(frame.itertuples(index=False))
    out = []
    for row in rows:
        for line in lines:
            if f"fuel {u.text(line[6])} mg/s" == row["notes"] and u.text(line[1]) in row["test_id"]:
                break
        out.append({**row, "_day": day(line[0]), "_on": clock(line[1]),
                    "_fuel": u.first(line[6]), "_air": u.first(line[8])})
    return out


def match(tests, d, on, fuel, air=None, strict=True):
    """The test of that day and ignition time whose fuel (and air) rate is closest. Strict: the
    rates must agree within 3 %; otherwise any test of that burn (smoke points were re-read from
    the video between the recorded flow steps)."""
    same = [t for t in tests if t["_day"] == d and t["_on"] == on and t["_fuel"] is not None]
    if not same or fuel is None:
        return None
    best = min(same, key=lambda t: (abs(t["_fuel"] - fuel), abs((t["_air"] or 0) - (air or 0))))
    return best if not strict or abs(best["_fuel"] - fuel) <= max(0.02, 0.03 * fuel) else None


def record() -> pd.DataFrame:
    raw = pd.read_excel(RECORD, sheet_name=0, header=None, engine="xlrd")
    frame = raw.iloc[4:, :28].copy()
    frame.columns = ["day", "date", "on", "off", "data", "sh", "lo", "no", "fuel", "nozzle", "pressure",
                     "fuel_display", "air_display", "fan", "rad", "gain", "length_mm", "sccm", "mg_s",
                     "hc_mg_s", "air_cm_s", "width_px", "width_mm", "height_px", "height_mm", "smoke_height",
                     "comment", "comment2"]
    frame["sheet_row"] = frame.index + 1  # 1-based spreadsheet row
    frame["d"] = frame["day"].map(day)
    frame["clock_on"] = frame["on"].map(clock)
    return frame[frame["d"].notna()]


OUTCOME_WORDS = [(r"blew off|blows? out|blew out", "blown off"), (r"ran ou[tr] of fuel", "fuel depleted"),
                 (r"fuel valve closed", "fuel valve closed")]


def record_facts(r) -> tuple[str, list[str]]:
    """Outcome and note parts of one record row."""
    notes, outcome = [], ""
    length = u.first(str(r["length_mm"]).lstrip("*")) if u.text(r["length_mm"]) else None
    if length:
        notes.append(f"luminous flame length {length:.1f} mm (video)")
    if u.first(r["height_mm"]):
        notes.append(f"flame length {u.first(r['height_mm']):.1f} mm, max width {u.first(r['width_mm']):.1f} mm (Nikon)")
    sh, lo = u.text(r["sh"]).lower(), u.text(r["lo"]).lower()
    if lo == "y":
        outcome = "lifted flame"
    if sh == "y":
        outcome = "smoke point reached"
    elif sh == "n" and not outcome:
        outcome = "no smoke point"
    comment = " ".join([u.text(r["comment"]), u.text(r["comment2"])]).lower()
    for pattern, word in OUTCOME_WORDS:
        if re.search(pattern, comment):
            outcome = word if word != "fuel valve closed" else outcome
            notes.append(word)
    if "exceeds" in comment:
        notes.append("flame exceeds camera frame")
    return outcome, notes


def smoke_points() -> pd.DataFrame:
    raw = pd.read_excel(SMOKE_POINTS, sheet_name="Smoke Point Datasheet", header=None)
    frame = raw.iloc[4:59, [0, 1, 2, 5, 6, 7, 18, 20, 27, 29]].copy()
    frame.columns = ["day", "on", "off", "sp_id", "fuel", "nozzle", "sp_mm", "width_mm", "mg_s", "air_cm_s"]
    frame["sheet_row"] = frame.index + 1
    return frame[frame["sp_id"].notna()]


def smoke_note(r) -> str:
    return (f"smoke point {r['sp_id']}: smoke point length {r['sp_mm']:.1f} mm at {r['mg_s']:.3f} mg/s fuel, "
            f"coflow {r['air_cm_s']:.1f} cm/s")


def smoke_point_tests() -> list[dict]:
    """Smoke points whose burn (day and ignition time) is in neither NASA's table nor the record."""
    tests = spice_tests()
    rows = []
    for _, r in smoke_points().iterrows():
        d, on = day(r["day"]), clock(r["on"])
        if any(t["_day"] == d and t["_on"] == on for t in tests):
            continue
        rows.append(spice_row(d, on, r["off"], r["fuel"], r["nozzle"], r["air_cm_s"], "smoke point reached",
                              [f"fuel {r['mg_s']:.3f} mg/s", smoke_note(r)],
                              f"{rel(SMOKE_POINTS)} (Smoke Point Datasheet, row {r['sheet_row']})"))
    return rows


def spice_row(d, on, off, fuel, nozzle, air, outcome, notes, source) -> dict:
    try:
        duration = (pd.Timedelta(clock(off)) - pd.Timedelta(on)).total_seconds()
    except ValueError:
        duration = None
    return {
        "psi_id": "PSI-107", "investigation": "SPICE", "test_id": f"{d}-{on}", "date": f"GMT day {d}",
        "fuel_type": "gas jet", "material": u.text(fuel), "material_family": u.text(fuel),
        "geometry": "coflow jet flame", "diameter_mm": u.first(nozzle), "o2_percent": 21,
        "flow_cm_s": round(u.first(air), 2) if u.first(air) is not None else None,
        "flow_direction": "concurrent", "ignited": "yes",
        "burn_time_s": duration if duration and duration > 0 else None, "outcome": outcome,
        "notes": "; ".join(notes), "source": source,
    }


def spice_updates() -> dict:
    tests = spice_tests()
    by_id = {t["test_id"]: t for t in tests}
    found: dict[str, dict] = {}

    def add(test, outcome, notes, source):
        cell = found.setdefault(test["test_id"], {"outcome": "", "notes": [], "sources": []})
        if outcome and not (cell["outcome"] == "smoke point reached" and outcome in ("lifted flame", "no smoke point")):
            cell["outcome"] = outcome
        cell["notes"] += [n for n in notes if n not in cell["notes"]]
        cell["sources"].append(source)

    for _, r in record().iterrows():
        test = match(tests, r["d"], r["clock_on"], u.first(r["mg_s"]), u.first(r["air_cm_s"]))
        outcome, notes = record_facts(r)
        if test and (outcome or notes):
            add(test, outcome, notes, f"{rel(RECORD)} (sheet 1, row {r['sheet_row']})")

    for _, r in smoke_points().iterrows():
        test = match(tests, day(r["day"]), clock(r["on"]), r["mg_s"], r["air_cm_s"], strict=False)
        if test is not None:  # burns missing from NASA's table become new tests (smoke_point_tests)
            add(test, "smoke point reached", [smoke_note(r)],
                f"{rel(SMOKE_POINTS)} (Smoke Point Datasheet, row {r['sheet_row']})")

    updates = {}
    for test_id, cell in found.items():
        fields = {}
        if cell["outcome"]:
            fields["outcome"] = cell["outcome"]
        if cell["notes"]:
            fields["notes"] = "; ".join([by_id[test_id]["notes"], *cell["notes"]])
        fields["_source"] = " | ".join(dict.fromkeys(cell["sources"]))
        updates[("PSI-107", test_id)] = fields
    return updates


def spice_new_tests() -> list[dict]:
    """Day 62 (2 March 2009, methane) is in the flight record but not in NASA's table. Its photo
    rows repeat the video rows with an ignition time 1 to 3 s later: they are merged into them."""
    tests = spice_tests()
    kept: dict[tuple, dict] = {}
    ignitions: dict[int, list[str]] = {}
    for _, r in record().iterrows():
        fuel, on = u.first(r["mg_s"]), r["clock_on"]
        if fuel is None or not re.fullmatch(r"\d+:\d\d:\d\d", on):
            continue
        if any(t["_day"] == r["d"] and t["_on"] == on for t in tests):
            continue
        d = int(r["d"])
        seconds = pd.Timedelta(on).total_seconds()
        on = next((o for o in ignitions.get(d, []) if abs(pd.Timedelta(o).total_seconds() - seconds) <= 5), on)
        if on not in ignitions.setdefault(d, []):
            ignitions[d].append(on)
        outcome, notes = record_facts(r)
        air = u.first(r["air_cm_s"])
        key = next((k for k in kept if k[0] == d and k[1] == on and abs(k[2] - fuel) <= max(0.02, 0.03 * fuel)
                    and abs(k[3] - (air or 0)) <= 0.5), None)
        if key:
            row = kept[key]
            row["notes"] += "".join(f"; {n}" for n in notes if n not in row["notes"])
            row["outcome"] = row["outcome"] or outcome
            continue
        kept[(d, on, fuel, air or 0)] = spice_row(d, on, r["off"], r["fuel"], r["nozzle"], air, outcome,
                                                  [f"fuel {fuel:.3f} mg/s", *notes],
                                                  f"{rel(RECORD)} (sheet 1, row {r['sheet_row']})")
    rows = list(kept.values()) + smoke_point_tests()
    ids = set()
    for row in rows:
        while row["test_id"] in ids:
            row["test_id"] += "b"
        ids.add(row["test_id"])
    return rows


# ---------------------------------------------------------------- SLICE

FUELS = {"CH4": "methane", "C2H4": "ethylene", "C2H6": "ethane", "C3H8": "propane"}


def slice_new_tests() -> list[dict]:
    frame, source = u.table(106)
    rows = []
    for _, r in frame.iterrows():
        written, fuel = u.text(r["Test Date"]), u.text(r["Fuel Type"])
        date = pd.to_datetime(written.split()[0], format="%Y-%b-%d")
        main = re.match(r"(\d+)% (\w+)", fuel)
        detail = re.sub(r"^\d+% \w+ ?(\(balance N2\))? ?", "", fuel)
        extra = re.sub(r"^\d{4}-\w{3}-\d{2} ?|SLICE testing with ?", "", written).strip()
        if extra.endswith("and then 100%"):  # the table splits this line in two cells
            extra = extra.replace("and then 100%", f"and then {fuel}")
        percent = int(main[1])
        rows.append({
            "psi_id": "PSI-106", "investigation": "SLICE", "test_id": date.strftime("%Y-%m-%d"),
            "date": date.strftime("%Y-%m-%d"), "fuel_type": "gas jet",
            "material": f"{percent}% {main[2]}" + (" in N2" if percent < 100 else ""),
            "material_family": FUELS.get(main[2], main[2]), "geometry": "coflow jet flame",
            "o2_percent": 21, "diluent": "N2" if percent < 100 else "", "flow_direction": "concurrent",
            "ignited": "yes",
            "notes": "; ".join(x for x in ["one row per day of operations (several flames and flow conditions)",
                                           extra, detail] if x),
            "source": source,
        })
    return rows


# ---------------------------------------------------------------- API

def new_tests() -> list[dict]:
    return spice_new_tests() + slice_new_tests()


def updates() -> dict:
    return {k: {f: v for f, v in fields.items() if not f.startswith("_")} for k, fields in spice_updates().items()}
