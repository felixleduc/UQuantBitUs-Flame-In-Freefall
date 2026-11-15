"""Readers for the smoke and aerosol investigations: PSI-102 SAME, PSI-101 SAME-R, PSI-47 DAFT.

    new_tests()  SAME flight runs (the 8 rows of the SAME table are a planned matrix, not runs)
                 and the DAFT-3 test points (cabin air 2006 and the three dust bags)
    updates()    SAME-R runs and DAFT sessions D1, D2 already in tests.csv
    proposed()   values for the 3 proposed columns (smoke_mean_diameter_um, smoke_number_per_cm3,
                 smoke_mass_mg_m3), long format, kept out of TEST_FIELDS

SAME and SAME-R per-test values come from the team's results workbook
(PSI-101 ... SAME, SAME-R_Results.xlsx), sheets "SAME1 Flight Tests 8-27-09" and "SAME R Results".
The per-run .xls files are 1 Hz time series that this workbook reduces; they are not re-read.

Detector reading rules (from the per-run time series and the SAME report):
    ISS light-scattering detector: baseline about 0.2 V, smoke raises it, it saturates near 6.3 V.
    STS (Shuttle) ionization detector: baseline about 5.13 V, smoke lowers it; near 0 V means
    it was not sampled in that run.
    Ion B: ionization chamber from a residential detector (delta volts above its offset).
"""

import html
import re
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
import unify_data as u

HERE = Path(__file__).resolve().parent
RESULTS = u.folder(101) / "Analyzed Data" / "Reduced Gravity" / "PSI-101_Analyzed Data_SAME, SAME-R_Results.xlsx"
MATERIAL = {  # names that unify_data.describe() maps to the right family
    "Silicone": "Silicone rubber", "Kapton": "Kapton", "Teflon": "Teflon", "Lampwick": "Lampwick (cellulose)",
    "DBP": "Dibutyl phthalate (DBP) in wick", "Pyrell": "Pyrell",
}
NO_IGNITION = {"fuel_type": "smoke", "ignited": "no", "outcome": "no ignition"}


def rel(path: Path) -> str:
    return str(path.relative_to(u.ROOT))


def num(value) -> float | None:
    v = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(v) else float(v)


def fmt(value, digits=3) -> str:
    return f"{value:.{digits}g}"


# ---------------------------------------------------------------- SAME and SAME-R

def detectors(iss, sts, sts_offset, ion_delta) -> str:
    """Which detectors saw the smoke, in words, with the reading behind each word."""
    out = []
    if iss is not None and abs(iss) > 0.01:
        level = "saturated" if iss >= 6 else "strong" if iss >= 2 else "weak" if iss >= 0.4 else "no response"
        out.append(f"ISS scattering detector {level} ({fmt(iss)} V, baseline 0.2 V)")
    if sts is not None and sts > 0.5:
        base = sts_offset if sts_offset and sts_offset > 0.5 else 5.13
        drop = base - sts
        out.append(f"STS ionization detector {'responded' if drop > 0.1 else 'no response'} (drop {fmt(drop, 2)} V)")
    if ion_delta is not None:
        out.append(f"ionization chamber {'responded' if ion_delta > 0.1 else 'no response'} (+{fmt(ion_delta, 2)} V)")
    return "; ".join(out)


def measurements(r) -> tuple[str, dict]:
    """Note text and proposed-column values of one reduced row (keys: M0, cmd, dam, sg, dtB, T, ml, ptrak)."""
    m0, cmd, dam, sg, dtb = (num(r.get(k)) for k in ("M0", "cmd", "dam", "sg", "dtB"))
    parts, cols = [], {}
    if m0:
        parts.append(f"number conc {m0:.3g} /cm3")
        cols["smoke_number_per_cm3"] = round(m0, -3)
    elif num(r.get("ptrak")) and num(r.get("ptrak")) > 0:
        parts.append(f"P-Trak {num(r.get('ptrak')):.3g} /cm3 (diluted reading, size not reduced)")
    if cmd:
        parts.append(f"count mean diameter {cmd:.3g} um")
        cols["smoke_mean_diameter_um"] = round(cmd, 3)
    if dam:
        parts.append(f"diameter of average mass {dam:.3g} um")
    if sg:
        parts.append(f"sigma_g {sg:.3g}")
    if dtb:
        parts.append(f"mass conc {dtb:.3g} mg/m3 (DustTrak, dilution corrected)")
        cols["smoke_mass_mg_m3"] = round(dtb, 2)
    if num(r.get("T")):
        parts.append(f"sample {num(r.get('T')):.0f} C")
    if num(r.get("ml")):
        parts.append(f"mass loss {num(r.get('ml')):.3g} mg")
    return "; ".join(parts), cols


def same_rows() -> pd.DataFrame:
    frame = pd.read_excel(RESULTS, sheet_name="SAME1 Flight Tests 8-27-09", header=None, skiprows=2)
    frame = frame[[1, 4, 5, 7, 11, 12, 13, 16, 23, 25, 26, 30, 33, 35, 36, 41, 42, 44, 59]]
    frame.columns = "mat id desc date v rt dur age ml iss sts ptrak ionBd dtB M0 cmd dam sg T".split()
    return frame[frame.mat.notna()]


def same_r_rows() -> pd.DataFrame:
    frame = pd.read_excel(RESULTS, sheet_name="SAME R Results", header=None, skiprows=2)
    frame = frame[[1, 5, 6, 8, 10, 11, 12, 17, 43, 44, 45, 50, 54, 55, 59, 60, 61, 64, 77, 78]]
    frame.columns = "mat id desc date v rt dur age iss sts stsoff ptrak ionBd M0 dtB cmd dam sg T ml".split()
    return frame[frame.mat.notna()]


def run_notes(r, setup: bool = True) -> tuple[str, dict]:
    """Run notes; setup=False leaves out what the SAME-R table already put in tests.csv."""
    text, cols = measurements(r)
    conditions = [u.text(r.desc), f"heater Rt/R0 {num(r.rt):.3g}" if num(r.rt) else "",
                  f"net aging {num(r.age):.0f} s" if num(r.age) else ""] if setup else []
    heated = f"heated {num(r.dur):g} s below ignition" if num(r.dur) else ""
    det = detectors(num(r.iss), num(r.sts), num(r.get("stsoff")), num(r.ionBd))
    return "; ".join(x for x in [*conditions, heated, text, det] if x), cols


def day(value) -> pd.Timestamp | None:
    stamp = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(stamp) else stamp


def same_id(value) -> str:
    """SAME numbers 1..47, aged readings carry an 'a': 'Run 05', 'Run 23a'."""
    raw = u.text(value)
    digits = "".join(c for c in raw if c.isdigit())
    return f"Run {int(digits):02d}{raw[len(digits):]}"


def same_tests() -> tuple[list[dict], dict]:
    rows, cols = [], {}
    for _, r in same_rows().iterrows():
        notes, extra = run_notes(r)
        material = MATERIAL[u.text(r.mat)]
        date = day(r.date)
        test_id = same_id(r.id)
        rows.append({
            "psi_id": "PSI-102", "investigation": "SAME", "test_id": test_id,
            "date": date.strftime("%Y-%m-%d") if date is not None else "",
            "material": material, **u.describe(material), **NO_IGNITION,
            "flow_cm_s": num(r.v), "notes": notes, "source": f"{rel(RESULTS)} (SAME1 Flight Tests 8-27-09)",
        })
        cols[("PSI-102", test_id)] = extra
    return rows, cols


TEM_TABLE = (u.folder(101) / "Analyzed Data" / "Reduced Gravity" / "Cotton Lamp wick" / "Run 054"
             / "PSI-101_Analyzed Data_Sample descriptions tables.docx")


def tem() -> dict[str, str]:
    """TEM morphology per SAME-R run ('62', '62a') from the Word table of thermal precipitator samples."""
    xml = zipfile.ZipFile(TEM_TABLE).read("word/document.xml").decode()
    table = re.search(r"<w:tbl>.*?</w:tbl>", xml, re.S).group(0)
    out = {}
    for row in re.findall(r"<w:tr[ >].*?</w:tr>", table, re.S)[1:]:
        cells = [u.text(html.unescape(" ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", c))))
                 for c in re.findall(r"<w:tc>.*?</w:tc>", row, re.S)]
        run = cells[1].lstrip("#") + ("a" if cells[3].lower() == "aged" else "")
        out[run] = "; ".join(x for x in [out.get(run, ""), cells[7].replace(" \u2013 ", ", ").replace("\u2013", "-").replace("\uf06d m", "um").replace("\uf06d", "u").rstrip(".")] if x)
    return out


def same_r_updates() -> tuple[list[dict], dict, dict]:
    """Updates for SAME-R runs in tests.csv; runs missing from its table (Kapton 112) become new tests."""
    tests = u.base_frame()
    tests = tests[tests.psi_id == "PSI-101"]
    known = {(r.material, r.test_id): r for r in tests.itertuples()}
    new, out, cols = [], {}, {}
    morphology = tem()
    for _, r in same_r_rows().iterrows():
        key = (u.text(r.mat), u.text(r.id))
        notes, extra = run_notes(r, setup=key not in known)
        if morphology.get(key[1]):
            notes += f"; TEM: {morphology[key[1]]}"
        update = {"ignited": "no", "outcome": "no ignition", "burn_time_s": "", "notes": notes}
        if day(r.date) is not None:
            update["date"] = day(r.date).strftime("%Y-%m-%d")
        if key[0] == "Pyrell":
            update["material_family"] = "Pyrell foam"
        if key not in known:
            material = MATERIAL[key[0]]
            new.append({"psi_id": "PSI-101", "investigation": "SAME-R", "test_id": key[1], "material": material,
                        **u.describe(material), **NO_IGNITION, **update, "flow_cm_s": num(r.v), "burn_time_s": None,
                        "source": f"{rel(RESULTS)} (SAME R Results)"})
            cols[("PSI-101", key[1])] = extra
            continue
        row = known[key]
        update["notes"] = f"{row.notes}; {notes}"
        out[("PSI-101", row.test_id)] = update
        cols[("PSI-101", row.test_id)] = extra
    return new, out, cols


# ---------------------------------------------------------------- DAFT

def xlsx(xls: Path) -> Path:
    """pandas reads .xls through xlrd: the file is used as is."""
    return xls


DAFT_ANALYZED = u.folder(47) / "Analyzed Data" / "Reduced Gravity"
SUMMARY = DAFT_ANALYZED / "PSI-47_Analyzed Data_DAFT Retrieved Data Summary.xls"


def raw_txt(path: Path) -> pd.Series:
    """A DAFT instrument log: header lines 'Key: value', then one reading per line."""
    values = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip().strip("\x00")
        if line and ":" not in line:
            values.append(float(line))
    return pd.Series(values)


def logged() -> dict[int, dict[str, pd.Series]]:
    """Readings of each instrument per logged test ID 1..7; tests 2-4 from the raw .txt files."""
    out = {}
    for sheet, name in [("Raw PTrak Data", "ptrak"), ("Raw DustTrak Data", "dtrak")]:
        frame = pd.read_excel(xlsx(SUMMARY), sheet_name=sheet)
        for i in range(1, 8):
            out.setdefault(i, {})[name] = pd.to_numeric(frame[f"Data{i}"], errors="coerce").dropna()
    raw = u.folder(47) / "Raw Data" / "Reduced Gravity"
    for i in (2, 3, 4):
        out[i]["ptrak"] = raw_txt(raw / "P-TRAK" / f"PSI-47_Raw Data_PTrk000{i}.txt")
        out[i]["dtrak"] = raw_txt(raw / "DustTrak" / f"PSI-47_Raw Data_DTrk000{i}.txt")
    return out


def log_note(i: int, data: dict) -> str:
    p, d = data["ptrak"], data["dtrak"]
    return (f"logged test {i}: P-Trak median {p.median():.3g} /cm3, 95th percentile {p.quantile(.95):.3g} /cm3 ({len(p)} s); "
            f"DustTrak median {d.median():.3g} mg/m3, 95th percentile {d.quantile(.95):.3g} mg/m3 ({len(d)} s)")


DAFT_PLACES = {1: "cabin air near EXPRESS rack 4", 2: "Velcro mated and demated in front of the inlet",
               3: "Lab, near Port rack 6", 4: "Node 1, mid-cabin", 5: "cabin air (DAFT-3 session, nominal plan aborted)"}


def daft() -> tuple[list[dict], dict, dict]:
    logs = logged()
    updates = {
        ("PSI-47", "D1"): {"date": "2005-02-22", "notes": f"{DAFT_PLACES[1]}; {log_note(1, logs[1])}"},
        ("PSI-47", "D2"): {"date": "2005-03-04", "notes": " | ".join(
            f"test point {i}, {DAFT_PLACES[i]}: {log_note(i, logs[i])}" for i in (2, 3, 4))},
    }
    cols = {("PSI-47", "D1"): {"smoke_number_per_cm3": round(logs[1]["ptrak"].median(), 1)}}
    source = f"{rel(SUMMARY)} (Raw PTrak Data, Raw DustTrak Data)"
    common = {"psi_id": "PSI-47", "investigation": "DAFT", "fuel_type": "aerosol", "material_family": "test dust"}
    new = [{**common, "test_id": "TP5", "date": "2006-08-17", "material": "ISS cabin air",
            "material_family": "", "notes": f"{DAFT_PLACES[5]}; {log_note(5, logs[5])}", "source": source}]
    cols[("PSI-47", "TP5")] = {"smoke_number_per_cm3": round(logs[5]["ptrak"].median(), 1)}

    voice = pd.read_excel(xlsx(SUMMARY), sheet_name="Voice Down Data Summary", header=None)
    for bag, (pc, dc) in enumerate([(1, 2), (4, 5), (7, 8)], start=1):
        p = pd.to_numeric(voice.iloc[2:, pc], errors="coerce")
        d = pd.to_numeric(voice.iloc[2:, dc], errors="coerce")
        series = voice.iloc[2:, 0].astype(str)
        stop = series[series.str.startswith("average")].index
        p, d = p.loc[:stop[0] - 1].dropna(), d.loc[:stop[0] - 1].dropna()
        mass_per_particle = d.mean() * 1e-9 / p.mean()  # g per particle: mg/m3 -> g/cm3, / (#/cm3)
        dam = (6 * mass_per_particle / 3.14159265) ** (1 / 3) * 1e4  # um, density 1 g/cm3 as in the report
        log = logs[6] if bag == 1 else logs[7]
        new.append({**common, "test_id": f"Bag {bag}", "date": "2006-08-21",
                    "material": "Arizona Road Dust (ARD Fine) dispersed with ISS GN2 in a 15 L bag, through the DAFT impactor",
                    "notes": (f"crew call-downs every 30 s: P-Trak mean {p.mean():.0f} /cm3, DustTrak mean {d.mean():.3g} mg/m3, "
                              f"diameter of average mass {dam:.2f} um (density 1); "
                              f"{log_note(6 if bag == 1 else 7, log)} (log assigned to bags by order, not certain)"),
                    "source": f"{rel(SUMMARY)} (Voice Down Data Summary)"})
        cols[("PSI-47", f"Bag {bag}")] = {"smoke_number_per_cm3": round(p.mean(), 0), "smoke_mass_mg_m3": round(d.mean(), 2)}
    return new, updates, cols


# ---------------------------------------------------------------- entry points

def _all():
    same_new, same_cols = same_tests()
    same_r_new, same_r_up, same_r_cols = same_r_updates()
    daft_new, daft_up, daft_cols = daft()
    return same_new + same_r_new + daft_new, {**same_r_up, **daft_up}, {**same_cols, **same_r_cols, **daft_cols}


def new_tests() -> list[dict]:
    return _all()[0]


def updates() -> dict:
    return _all()[1]


def proposed() -> dict:
    return _all()[2]
