"""Merge the downloaded PSI files into three tables with common columns.

    data/processed/investigations.csv   one row per PSI investigation (from its metadata archive)
    data/processed/tests.csv            one row per test, same columns for every investigation
    data/processed/context.csv          facts read in reports and notes, each with its quote,
                                        file and page (written by hand, not by this script)

Numbers come from tables (experimental tables, test matrices), then from the per-test files
that the modules of src/readers/ read (logs, sensor sheets, summaries). A value in context.csv
whose test_id is filled and whose field is a column of tests.csv fills or corrects that cell,
so outcomes described in prose land next to the conditions they belong to.

Usage:
    uv run python src/download_psi_files.py     # first, once: the files this script reads
    uv run python src/unify_data.py
"""

import csv
import functools
import io
import re
import zipfile
from pathlib import Path

import pandas as pd

from list_psi_files import INVESTIGATIONS, ROOT

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
URL = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-{id}"

GROUPS = {  # role of each investigation for the dashboard question
    "solid materials": [99, 98, 100, 25, 26],
    "fuel and flame physics": [69, 68, 39, 159, 10, 20],
    "smoke detection": [102, 101, 47],
    "flame structure": [107, 106, 22, 23, 21],
}

TEST_FIELDS = [
    "psi_id", "investigation", "test_id", "date", "fuel_type", "material", "material_family",
    "geometry", "thickness_mm", "width_cm", "length_cm", "diameter_mm", "o2_percent", "co2_percent",
    "pressure_atm", "diluent", "flow_cm_s", "flow_steps_cm_s", "flow_direction", "ignited", "outcome",
    "burn_time_s", "spread_rate_mm_s", "o2_final_percent", "extinction_diameter_mm", "burning_rate_mm2_s",
    "cool_flame", "lifted", "peak_heat_flux_kw_m2", "peak_sample_temp_c", "fuel_percent", "flame_length_mm",
    "smoke_point_length_mm", "smoke_mean_diameter_um", "smoke_number_per_cm3", "smoke_mass_mg_m3",
    "notes", "source",
]

# Measurements the readers wrote into `notes`, moved to their own column (first pattern that matches wins)
FROM_NOTES = {
    "o2_final_percent": [r"final O2 ([\d.]+) ?%", r"O2 [\d.]+ > ([\d.]+) %"],
    "extinction_diameter_mm": [r"extinction diameter ([\d.]+) mm"],
    "burning_rate_mm2_s": [r"hot flame burning rate ([\d.]+) mm2/s", r"burning rate ([\d.]+) mm2/s"],
    "peak_heat_flux_kw_m2": [r"peak radiometer rise after igniter ([\d.]+) mW/cm2"],  # converted below
    "peak_sample_temp_c": [r"peak sample TC (-?[\d.]+) C"],
    "fuel_percent": [r"fuel ([\d.]+) % in fuel stream"],
    "flame_length_mm": [r"luminous flame length ([\d.]+) mm", r"flame length ([\d.]+) mm"],
    "smoke_point_length_mm": [r"smoke point length ([\d.]+) mm"],
    "smoke_mean_diameter_um": [r"count mean diameter ([\d.]+) um"],
    "smoke_number_per_cm3": [r"number conc ([\d.]+e[+-]\d+|[\d.]+) /cm3"],
    "smoke_mass_mg_m3": [r"mass conc ([\d.]+) mg/m3"],
}


def measured_columns(test: dict) -> None:
    """Fill the measurement columns from the notes and the outcome, when the readers left them empty."""
    notes, outcome = test.get("notes") or "", (test.get("outcome") or "").lower()
    for field, patterns in FROM_NOTES.items():
        if test.get(field) in (None, ""):
            match = next((m for p in patterns if (m := re.search(p, notes))), None)
            if match:
                value = float(match.group(1))
                test[field] = round(value * 0.01, 4) if field == "peak_heat_flux_kw_m2" else value  # 1 mW/cm2 = 0.01 kW/m2
    # Known typos in the BASS-II table (final O2 of 0.6 % or 39.1 %) and "0" written for "not seen"
    if test.get("o2_final_percent") not in (None, "") and not 10 <= float(test["o2_final_percent"]) <= 30:
        test["o2_final_percent"] = ""
    if test.get("extinction_diameter_mm") not in (None, "") and float(test["extinction_diameter_mm"]) == 0:
        test["extinction_diameter_mm"] = ""
    if not test.get("cool_flame"):
        if "probable cool flame" in outcome:
            test["cool_flame"] = "probable"
        elif "cool flame" in outcome or "cool flame burning rate" in notes:
            test["cool_flame"] = "yes"
    if not test.get("lifted") and outcome == "lifted flame":
        test["lifted"] = "yes"
INVESTIGATION_FIELDS = [
    "psi_id", "acronym", "title", "group", "tests", "platform", "hardware", "nasa_center",
    "start_date", "end_date", "principal_investigator", "topics", "objective", "hypothesis",
    "approach", "research_impacts", "doi", "publications", "url",
]
CONTEXT_FIELDS = ["psi_id", "test_id", "field", "value", "quote", "file", "page"]


# ---------------------------------------------------------------- reading values

def numbers(text) -> list[float]:
    """Every number in a cell: '10, 6, and 5' gives [10, 6, 5]; '037 mm' gives [0.37]."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return []
    if isinstance(text, (int, float)):
        return [float(text)]
    found = re.findall(r"\d*\.\d+|\d+(?:/\d+)?", str(text))
    values = []
    for n in found:
        if "/" in n:
            a, b = n.split("/")
            values.append(int(a) / int(b))
        elif re.fullmatch(r"0\d+", n):  # '037' is a typo for 0.37 in the Saffire-II table
            values.append(float("0." + n[1:]))
        else:
            values.append(float(n))
    return values


def first(text) -> float | None:
    found = numbers(text)
    return found[0] if found else None


def steps(text) -> str:
    """The successive flow settings of a test, as '10 > 6 > 5'."""
    return " > ".join(f"{n:g}" for n in numbers(text))


def percent(fraction) -> float | None:
    """O2 is written as 0.21 in some tables and 21 in others."""
    value = first(fraction)
    if value is None:
        return None
    return round(value * 100, 2) if value <= 1 else value


def text(value) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else " ".join(str(value).split())


INCH = 25.4
FAMILIES = [  # first match wins
    (r"sibal|cotton", "SIBAL cotton-fiberglass fabric"),
    (r"nomex", "Nomex"),
    (r"ultem", "Ultem"),
    (r"silicone", "silicone"),
    (r"kapton", "Kapton"),
    (r"teflon|ptfe", "Teflon"),
    (r"japan wax", "Japan wax"),
    (r"wax|candle|paraf", "paraffin wax"),
    (r"lampwick", "lampwick"),
    (r"phthalate", "dibutyl phthalate"),
    (r"pmma|rod|spher|film|slab|micron|mm thick|plexi", "PMMA"),
]


def describe(material: str) -> dict:
    """Family, shape and size of a solid sample from its free-text description."""
    low = material.lower()
    family = next((name for pattern, name in FAMILIES if re.search(pattern, low)), "")
    geometry = next((g for p, g in [(r"rod|cylinder", "rod"), (r"spher", "sphere"), (r"candle", "candle"),
                                    (r"fabric|sibal|nomex", "fabric"), (r"film|micron", "thin sheet"),
                                    (r"slab|sheet|mm thick|thick", "slab")] if re.search(p, low)), "")
    out = {"material_family": family, "geometry": geometry}
    if inch := re.search(r"(\d+/\d+|\d*\.\d+|\d+)\s*\"", material) or re.search(r"(\d+/\d+)(?= )", material):
        out["diameter_mm"] = round(numbers(inch.group(1))[0] * INCH, 2)
    if micron := re.search(r"(\d+)\s*micron", low):
        out["thickness_mm"] = int(micron.group(1)) / 1000
    elif thick := re.search(r"(\d*\.?\d+)\s*mm(?: thick)?(?! wide)", low):
        out["thickness_mm"] = float(thick.group(1))
    if wide := re.search(r"(\d*\.?\d+)\s*cm(?! thick)", low) or re.search(r"(\d*\.?\d+)\s*cm", low):
        size = float(wide.group(1))
        if geometry == "sphere":
            out["diameter_mm"] = size * 10
        else:
            out["width_cm"] = size
            out["geometry"] = geometry or "flat sheet"
    return out


# ---------------------------------------------------------------- one reader per investigation

def folder(psi_id: int) -> Path:
    return next(RAW.glob(f"PSI-{psi_id}_*"))


def table(psi_id: int, name: str = "") -> tuple[pd.DataFrame, str]:
    path = next(p for p in (folder(psi_id) / "Experimental table").glob("*.csv") if name in p.name)
    raw = path.read_bytes()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:  # some tables were saved by Excel on Windows
        content = raw.decode("cp1252")
    frame = pd.read_csv(io.StringIO(content), dtype=str, keep_default_na=False)
    frame.columns = [" ".join(c.split()) for c in frame.columns]
    return frame, str(path.relative_to(ROOT))


def bass() -> list[dict]:
    path = folder(26) / "Science Documents" / "PSI-26_Science Documents_As Run_Test Matrix.xlsx"
    frame = pd.read_excel(path, sheet_name="as run matrix", header=2, engine="openpyxl")
    frame.columns = [" ".join(str(c).split()).split(" (")[0] for c in frame.columns]
    rows, seen = [], set()
    for _, r in frame.iterrows():
        material = text(r["material"])
        if not material or first(r["As run test no."]) is None:
            continue
        # Test numbers 24, 85 and 89 to 91 are used twice: the second one becomes 24b, 85b...
        test_id = f"{int(first(r['As run test no.']))}"
        while test_id in seen:
            test_id += "b"
        seen.add(test_id)
        # "PMMA 2 cm" and "PMMA 1 cm" are spheres: the crew notes of those tests describe a sphere.
        if re.fullmatch(r"pmma [12] cm", material.lower()):
            material += " sphere"
        pressure = round(first(r["pressure, atm"]), 3) if first(r["pressure, atm"]) else None
        co2_mmhg = first(r["CO2, mm Hg"])
        rows.append({
            "test_id": test_id, "date": str(r.iloc[0])[:10],
            "fuel_type": "solid", "material": material, **describe(material),
            "o2_percent": percent(r["O2 % by volume"]), "pressure_atm": pressure,
            "co2_percent": round(co2_mmhg / (760 * pressure) * 100, 3) if co2_mmhg and pressure else None,
            "diluent": "N2", "flow_cm_s": first(r["Air display"]), "flow_steps_cm_s": steps(r["Air display"]),
            "notes": text(r["Test Observations and Anomalies"]),
            "source": f"{path.relative_to(ROOT)} (as run matrix, planned test {text(r['Test no.'])})",
        })
    return rows


# Flow geometry of each BASS-II principal investigator, from the BASS-II ReadMe
BASS2_DIRECTION = {"Olson": "concurrent", "Fernandez-Pello": "opposed", "T'ien": "concurrent"}


def bass2() -> list[dict]:
    frame, source = table(25)
    rows = []
    for _, r in frame.iterrows():
        material = text(r["Fuel Sample Material"])
        o2_start, o2_end = first(r["Calibrated initial O2 % by vol"]), first(r["Calibrated final O2 % by vol"])
        rows.append({
            # T9 and T18 are dated 2018 by mistake: BASS-II flew in 2014 and their GMT day (175) matches
            "test_id": text(r["Test #"]), "date": text(r["Date"]).replace("/2018", "/2014"), "fuel_type": "solid",
            "material": material, **describe(material),
            "o2_percent": o2_start, "co2_percent": first(r["Initial CO2 % by vol"]), "pressure_atm": None,
            "diluent": "N2", "flow_cm_s": first(r["Air display"]), "flow_steps_cm_s": steps(r["Air display"]),
            "flow_direction": BASS2_DIRECTION.get(text(r["PI"]), ""),
            "notes": f"PI {text(r['PI'])}; final O2 {o2_end} %; fan: {text(r['Fan display'])}",
            "source": source,
        })
    return rows


def saffire(psi_id: int) -> list[dict]:
    frame, source = table(psi_id)
    frame = frame[frame.iloc[:, 0].str.match(r"^(S\d|\d-\d)")]
    cols = {re.sub(r"\W", "", c.lower()): c for c in frame.columns}

    def get(r, *keys):
        return next((r[cols[k]] for k in keys if k in cols), "")

    rows, material = [], ""
    for _, r in frame.iterrows():
        material = text(r["Material"]) or material  # blank means same as the sample above
        written = text(get(r, "samplethicknesscm", "samplethickness", "samlethickness"))
        thickness = None if "see" in written.lower() else first(written)
        # Saffire-I and III give the SIBAL fabric as 0.37 and 0.33 "cm"; Saffire-II lists the same
        # fabric at 0.37 mm, so their unit is read as mm for that fabric.
        if thickness is not None and written.endswith(" cm") and "sibal" not in material.lower():
            thickness *= 10
        length, width = first(get(r, "samplelengthcm", "samplelength")), first(get(r, "samplewidthcm", "samplewidth"))
        if length and width and width > length:  # Saffire-I swaps them: its samples are 40.6 cm wide, 94 cm long
            length, width = width, length
        spread = text(get(r, "gspreadlength"))
        burn = text(get(r, "burntimes"))
        mu_burn = text(get(r, "gburnlength"))
        rows.append({
            "test_id": text(r.iloc[0]), "fuel_type": "solid", "material": material, **describe(material),
            "thickness_mm": thickness, "length_cm": length, "width_cm": width, "geometry": "flat sheet",
            "o2_percent": first(get(r, "percento2", "percento2note1")),
            "flow_cm_s": first(get(r, "airflowcms", "airflow")),
            "flow_direction": text(get(r, "flowdirection", "direction")).lower(),
            "burn_time_s": first(burn) if "insignificant" not in burn.lower() else 0,
            "spread_rate_mm_s": first(spread) if "mm/s" in spread else None,
            "notes": "; ".join(f"{k}: {text(get(r, c))}" for k, c in [
                ("ignition", "ignitionpowerw"), ("microgravity burn length", "gburnlength"),
                ("1-g burn length", "1gburnlength"), ("1-g spread", "1gspreadrate")] if text(get(r, c))),
            "outcome": ("did not sustain" if mu_burn.startswith("~ 0") else
                        "burned" if mu_burn else ""),
            "source": source,
        })
    return rows


def flex() -> list[dict]:
    frame, source = table(69)
    rows = []
    for _, r in frame.iterrows():
        gases = {g: first(r[f"{g} initial ambient composition; mole fraction"]) or 0 for g in ["O", "N", "CO", "He"]}
        rows.append({
            "test_id": text(r["FLEX Test #"]), "date": text(r["Test Date"]), "fuel_type": "droplet",
            "material": text(r["Fuel"]), "material_family": text(r["Fuel"]), "geometry": "droplet",
            "diameter_mm": first(r["Droplet initial diameter; mm"]),
            "o2_percent": percent(gases["O"]), "co2_percent": percent(gases["CO"]) if gases["CO"] else 0,
            "pressure_atm": round(first(r["Ambient pressure; mmHg"]) / 760, 3) if first(r["Ambient pressure; mmHg"]) else None,
            "diluent": "+".join(n for g, n in [("N", "N2"), ("CO", "CO2"), ("He", "He")] if gases[g]),
            "burn_time_s": first(r["Burn time; s"]), "outcome": text(r["Test end"]).lower(),
            "extinction_diameter_mm": first(r["Visible flame extinction diameter; mm"]),
            "burning_rate_mm2_s": first(r["Burning rate; mm"]),  # the table header says mm, the unit is mm2/s
            "ignited": "yes" if first(r["Burn time; s"]) else "",
            "notes": f"FLEX id {text(r['FLEX Identifier'])}; extinction diameter {text(r['Visible flame extinction diameter; mm'])} mm; "
                     f"burning rate {text(r['Burning rate; mm'])} mm2/s",
            "source": source,
        })
    return rows


def cfi() -> list[dict]:
    frame, source = table(39)
    return [{
        "test_id": text(r["Flex Number"]), "date": text(r["Test Date"]), "fuel_type": "droplet",
        "material": text(r["Fuel"]), "material_family": text(r["Fuel"]), "geometry": "droplet",
        "o2_percent": percent(r["Oxygen"]), "pressure_atm": first(r["Pressure"]),
        "diluent": "+".join(n for c, n in [("Nitrogen", "N2"), ("Helium", "He")] if first(r[c])),
        "notes": f"fiber-supported: {text(r['Fiber'])}; CIR id {text(r['CIR'])}", "source": source,
    } for _, r in frame.iterrows()]


def gas_flames(psi_id: int) -> list[dict]:
    """Flame Design and CFI-G: one table of normal flames (fuel into air), one of inverse flames."""
    rows = []
    for kind in ["Normal", "Inverse"]:
        frame, source = table(psi_id, kind)
        cols = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in frame.columns}

        def get(r, *keys):
            return next((r[cols[k]] for k in keys if k in cols), "")

        for _, r in frame.iterrows():
            if not text(get(r, "test")):
                continue
            ending = text(get(r, "selfextorflowterm"))
            hot = text(get(r, "hotignition")).lower()
            fuel = text(get(r, "fuel")) or "C2H4"
            rows.append({
                "test_id": text(get(r, "test")), "date": f"day {text(get(r, 'day'))}", "fuel_type": "gas jet",
                "material": fuel, "material_family": fuel, "geometry": f"{kind.lower()} spherical flame",
                "o2_percent": percent(get(r, "xo2init", "xo2beforetest", "xo2")),
                "pressure_atm": first(get(r, "pmeanatm")) or (round(first(get(r, "approxpbar")) / 1.01325, 3)
                                                             if first(get(r, "approxpbar")) else None),
                "ignited": hot if hot in ("yes", "no") else "",
                "burn_time_s": first(get(r, "burntimesec")),
                "cool_flame": next((w for w in ("yes", "no") if text(get(r, "coolflame")).lower().startswith(w)), ""),
                "outcome": {"SE": "self-extinguished", "FT": "flow terminated"}.get(ending, ending.strip("-")),
                "notes": "; ".join(x for x in [f"oxidizer O2 fraction {text(get(r, 'xo2'))}" if kind == "Inverse" else "",
                                               f"adiabatic flame {text(get(r, 'tadk'))} K" if text(get(r, "tadk")) else "",
                                               text(get(r, "comments"))] if x),
                "source": source,
            })
    return rows


def spice() -> list[dict]:
    frame, source = table(107)
    rows = []
    for i, r in frame.iterrows():
        on, off = text(r["GMT ignition"]), text(r["GMT Flame Off"])
        try:
            duration = (pd.Timedelta(off) - pd.Timedelta(on)).total_seconds()
        except ValueError:
            duration = None
        rows.append({
            "test_id": f"{text(r['GMT date'])}-{on}", "date": f"GMT day {text(r['GMT date'])}",
            "fuel_type": "gas jet", "material": text(r["Fuel"]), "material_family": text(r["Fuel"]),
            "geometry": "coflow jet flame", "diameter_mm": first(r["Nozzle (mm)"]), "o2_percent": 21,
            "flow_cm_s": first(r["Air Rate (cm/s)"]), "flow_direction": "concurrent",
            "burn_time_s": duration if duration and duration > 0 else None,
            "notes": f"fuel {text(r['Fuel Rate (mg/s)'])} mg/s", "source": source,
        })
    return rows


def same_r() -> list[dict]:
    frame, source = table(101)
    return [{
        "test_id": text(r["SAME Test #"]), "date": text(r["Date"]), "fuel_type": "smoke",
        "material": text(r["Sample Type"]), **describe(text(r["Sample Type"])),
        "flow_cm_s": first(r["Inlet velocity (cm/s)"]), "burn_time_s": first(r["Duration (sec)"]),
        "notes": f"{text(r['Description'])}; heater Rt/R0 {text(r['Rt/R0'])}; net aging {text(r['Net aging time (sec)'])} s",
        "source": source,
    } for _, r in frame.iterrows() if text(r["Sample Type"])]


def daft() -> list[dict]:
    frame, source = table(47)
    return [{
        "test_id": text(r["Session Name"]), "date": text(r["Actual Day"]), "fuel_type": "aerosol",
        "material": text(r["Sample Material"]), "material_family": "test dust",
        "notes": f"{text(r['Hardware Description'])}; {text(r['Sampled Location'])}", "source": source,
    } for _, r in frame.iterrows()]


READERS = {
    26: bass, 25: bass2, 98: lambda: saffire(98), 99: lambda: saffire(99), 100: lambda: saffire(100),
    69: flex, 39: cfi, 10: lambda: gas_flames(10), 159: lambda: gas_flames(159), 107: spice,
    101: same_r, 47: daft,
}
# Not read as tests: FLEX-2 (its table gives ranges per fuel, not tests), the ACME campaigns
# (BRE, CLD Flame, E-FIELD Flames, s-Flame) and SLICE (one line per day of operations).


# ---------------------------------------------------------------- investigations

def metadata(psi_id: int) -> dict:
    archive = next((folder(psi_id) / "Investigation Metadata Files").glob("*.zip"))
    with zipfile.ZipFile(archive) as z:
        content = z.read("i_Investigation.txt").decode("utf-8", "replace")
    fields = {}
    for line in csv.reader(io.StringIO(content), delimiter="\t"):
        if line:
            fields.setdefault(line[0].strip(), [v.strip() for v in line[1:]])

    def one(key):
        return " ".join(" ".join(fields.get(key, [""])).split())

    roles = fields.get("Study Person Roles", [])
    people = [f"{f} {l}".strip() for f, l in zip(fields.get("Study Person First Name", []), fields.get("Study Person Last Name", []))]
    pis = [p for p, role in zip(people, roles) if "Principal" in role]
    return {
        "acronym": one("Comment[Investigation Acronym]"), "title": one("Study Title"),
        "platform": one("Comment[Flight Platform]"), "hardware": one("Comment[Experiment Hardware]"),
        "nasa_center": one("Comment[Managing NASA Center]"),
        "start_date": one("Comment[Investigation Start Date]"), "end_date": one("Comment[Investigation End Date]"),
        "principal_investigator": "; ".join(pis),
        "topics": "; ".join(t for t in fields.get("Study Design Type", []) if t),
        "objective": one("Comment[Objective]"), "hypothesis": one("Comment[Hypothesis]"),
        "approach": one("Comment[Approach]"), "research_impacts": one("Comment[Research Impacts]"),
        "doi": one("Comment[DOI]"),
        "publications": sum(1 for t in fields.get("Study Publication Title", []) if t),
    }


# ---------------------------------------------------------------- merge

def apply_context(tests: list[dict], context: list[dict]) -> None:
    """Fill or correct test cells with facts read in reports (context.csv rows with a test_id)."""
    index = {(t["psi_id"], t["test_id"]): t for t in tests}
    for fact in context:
        test = index.get((fact["psi_id"], fact["test_id"]))
        if test is not None and fact["field"] in TEST_FIELDS and fact["field"] not in ("psi_id", "test_id"):
            test[fact["field"]] = fact["value"]
        elif fact["test_id"] and test is None:
            print(f"  context.csv: no test {fact['test_id']} in {fact['psi_id']}")


def unique(rows: list[dict]) -> list[dict]:
    """Drop rows NASA lists twice (SPICE, CFI) and tell apart two tests sharing a number (SAME-R)."""
    kept, seen, ids = [], set(), set()
    for row in rows:
        key = tuple(sorted((k, str(v)) for k, v in row.items()))
        if key in seen:
            continue
        seen.add(key)
        while row["test_id"] in ids:
            row["test_id"] += "b"
        ids.add(row["test_id"])
        kept.append(row)
    return kept


def iso_date(value) -> str:
    """Calendar dates as YYYY-MM-DD; mission days ('day 3', 'GMT day 45') and dates without a year stay as written."""
    value = text(value)
    for pattern in ["%m/%d/%Y", "%Y-%m-%d", "%d-%b-%y", "%m/%d/%y"]:
        try:
            return pd.to_datetime(value, format=pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return value


@functools.cache
def base_frame() -> pd.DataFrame:
    """Tests read from the experimental tables and test matrices only, as text ("" when empty).
    The readers in src/readers/ compare their per-test files with it."""
    rows = []
    for psi_id, name in INVESTIGATIONS:
        for row in unique(READERS[psi_id]() if psi_id in READERS else []):
            row.update(psi_id=f"PSI-{psi_id}", investigation=name, date=iso_date(row.get("date")))
            rows.append(row)
    frame = pd.DataFrame(rows).reindex(columns=TEST_FIELDS)
    return frame.astype(object).where(frame.notna(), "").astype(str)


def from_files(tests: list[dict]) -> list[dict]:
    """Add the tests and values the readers of src/readers/ find in the per-test files."""
    from readers import acme, acme_gas, flex, smoke, solids, spice_slice

    index = {(t["psi_id"], t["test_id"]): t for t in tests}
    for module in [acme, acme_gas, flex, smoke, solids, spice_slice]:
        added = 0
        for row in module.new_tests():
            key = (row["psi_id"], row["test_id"])
            if key in index:
                print(f"  {module.__name__}: {key} already exists, kept the first")
                continue
            row["date"] = iso_date(row.get("date"))
            index[key] = row
            tests.append(row)
            added += 1
        changes = module.updates()
        for key, values in changes.items():
            if key not in index:
                print(f"  {module.__name__}: no test {key} to update")
                continue
            for field, value in values.items():
                value = value[0] if isinstance(value, tuple) else value  # some readers give (value, source)
                if field in TEST_FIELDS:
                    index[key][field] = value  # an empty value clears the cell (e.g. a heating time read as a burn time)
        print(f"{module.__name__:<20} {added:>5} new tests, {len(changes):>5} tests updated")
    return tests


SAME_OUTCOME = {  # labels the readers wrote differently for the same thing
    "burned to completion": "burned out",
    "brief flame, no spread": "brief flame",
    "no sustained ignition": "brief flame",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    context_path = OUT / "context.csv"
    if not context_path.exists():
        context_path.write_text(",".join(CONTEXT_FIELDS) + "\n")
    with context_path.open(encoding="utf-8") as f:
        context = list(csv.DictReader(f))

    tests = from_files([{k: v for k, v in r.items() if v != ""} for r in base_frame().to_dict("records")])
    apply_context(tests, context)
    for test in tests:  # a test with a recorded burn time ignited
        if not test.get("ignited") and float(test.get("burn_time_s") or 0) > 0:
            test["ignited"] = "yes"
            if test["fuel_type"] == "solid" and not test.get("outcome"):
                test["outcome"] = "burned"

    for test in tests:
        test["outcome"] = SAME_OUTCOME.get(test.get("outcome"), test.get("outcome"))
        measured_columns(test)
        for field in ["o2_percent", "pressure_atm"]:  # a burning test cannot have 0 % O2 or 0 atm: missing value
            if test.get(field) not in (None, "") and float(test[field]) == 0:
                test[field] = ""
        for field, value in test.items():  # no en or em dashes in what the team ships
            if isinstance(value, str):
                test[field] = value.replace(" \u2013 ", ", ").replace(" \u2014 ", ", ").replace("\u2013", "-").replace("\u2014", "-")

    group_of = {i: g for g, ids in GROUPS.items() for i in ids}
    counts = pd.Series([t["psi_id"] for t in tests]).value_counts()
    investigations = [{"psi_id": f"PSI-{i}", "group": group_of[i], "tests": int(counts.get(f"PSI-{i}", 0)),
                       "url": URL.format(id=i), **metadata(i)} for i, _ in INVESTIGATIONS]
    for name, fields, rows in [("tests.csv", TEST_FIELDS, tests), ("investigations.csv", INVESTIGATION_FIELDS, investigations)]:
        frame = pd.DataFrame(rows).reindex(columns=fields)
        frame.to_csv(OUT / name, index=False)
        print(f"{name}: {len(frame)} rows")


if __name__ == "__main__":
    main()
