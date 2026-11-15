"""Tests of the four ACME gas-flame campaigns (BRE, CLD Flame, E-FIELD Flames, s-Flame).

One test per test point (TP id such as 19039C1 = test day 19039, sequence C, run 1), merged from
    as-run parameter files ('as run<TP>.txt', '<TP>.txt', '<TP>_VoltageSweep.txt'): commanded flows,
        fuel concentration, coflow velocity, electric-field voltages
    timing files ('<TP>_TP.txt'): ignition, extinction detected, flows off, abort reason
    CIR chamber calculators ('Final ACME Chamber Calculator ... .xlsx', EventData sheet): ignition
        yes/no decided during operations, chamber pressure and gas composition before each test
        (BRE and CLD Flame days only; it also lists test points without downlinked files)
    experimental tables: fuel bottle and atmosphere of each test day.

Usage: <repo>/.venv/bin/python -I readers.py   (writes new_tests.csv and updates.csv next to this file)
"""

import csv
import re
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl

REPO = Path(__file__).resolve().parents[2]
from unify_data import INVESTIGATIONS, ROOT, TEST_FIELDS, first, folder, table, text

HERE = Path(__file__).parent
PSI_IDS = [20, 21, 22, 23]
TP_ID = re.compile(r"(\d{5}[A-Z]\d+(?:_\d)?)")  # 20346L3_1 is a rerun of 20346L3
PSIA_PER_ATM = 14.696
BRIEF_S = 3  # an extinction this soon after the igniter fired is a flame that did not hold

# Flame shape per campaign; E-FIELD changes burner between its two rounds (experimental table)
GEOMETRY = {20: "porous burner (BRE)", 21: "coflow jet flame", 22: "coflow jet flame", 23: "spherical burner flame"}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def day_of(test_id: str) -> str:
    return test_id[:5]


def iso(day: str) -> str:
    """Test day YYDDD (GMT day the test day began) as a calendar date."""
    return (datetime(2000 + int(day[:2]), 1, 1) + timedelta(days=int(day[2:]) - 1)).strftime("%Y-%m-%d")


def untypo(label: str) -> str:
    """Undo the Excel fill-down typos of the experimental tables ('40% CH5', '100% C2H9', 'with N3')."""
    label = re.sub(r"\bN\d\b", "N2", text(label))
    return re.sub(r"C2H\d+", "C2H4", re.sub(r"\bCH\d+", "CH4", label))


def fuel_of(bottle: str) -> tuple[str, str]:
    """Fuel species and bottle from a bottle label."""
    bottle = untypo(bottle)
    species = [s for s in ["H2", "CH4", "C2H4"] if re.search(rf"\b{s}\b", bottle)]
    return "+".join(species), bottle


# ---------------------------------------------------------------- day tables

def days(psi_id: int) -> dict[str, dict]:
    """Experimental table rows by test day."""
    if psi_id == 20:
        return BRE_DAYS
    frame, source = table(psi_id)
    out, last = {}, None
    for _, r in frame.iterrows():
        row = {k: text(v) for k, v in r.items()}
        day = row.get("Test Day") or row.get("Test Day*")
        if day:
            row["source"] = source
            out[day] = last = row
        elif last is not None and row.get("Fuel Conc"):  # E-FIELD continuation rows list more concentrations
            last["Fuel Conc"] += "; " + row["Fuel Conc"]
    return out


# BRE's experimental table has no test day column and shifts several 2020 dates (Oct 17 for Sept 17,
# Dec 4/5 swapped): its days come from Table 1 of the BRE test summary (Science Documents,
# ACME-BRE_Test_Summary.docx, an image), with the burner of each day. The calculator names each fuel.
BRE_DAYS = {day: {"Fuel Bottle": bottle, "burner_mm": 50 if day in ("20247", "21028") else 25}
            for day, bottle in [
                ("19039", "100% C2H4"), ("19051", "100% C2H4"), ("19056", "50% C2H4"), ("19063", "50% C2H4"),
                ("19066", "50% C2H4"), ("19070", "50% C2H4"), ("19087", "100% C2H4"), ("19091", "100% C2H4"),
                ("19094", "100% C2H4"), ("20247", "100% C2H4"), ("20261", "100% C2H4"), ("20279", "100% CH4"),
                ("20339", "100% CH4"), ("20346", "50% C2H4"), ("20352", "100% C2H4"), ("20358", "100% C2H4"),
                ("21020", "100% C2H4"), ("21028", "100% C2H4")]}


# ---------------------------------------------------------------- files

def parse(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(errors="replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values.setdefault(key.strip().strip("\\'"), value.strip().rstrip(","))
    return values


def stamp(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(text(value), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def test_point_files(psi_id: int) -> dict[str, dict]:
    """{tp: {'run': as-run values, 'timing': timing values, 'files': [...]}} for every .txt of the campaign."""
    points = {}
    for path in sorted(folder(psi_id).rglob("*.txt")):
        values = parse(path)
        found = TP_ID.search(path.name) or TP_ID.search(values.get("Test Point", "") + values.get("testpointName", ""))
        if not found or not values:
            continue
        point = points.setdefault(found.group(1), {"run": {}, "timing": {}, "files": []})
        kind = "timing" if "Script start" in values or "Test Point" in values else "run"
        for k, v in values.items():
            point[kind].setdefault(k, v)
        point["files"].append(rel(path))
    return points


def calculator() -> dict[str, dict]:
    """Chamber calculator EventData rows of type TP, by test point id (first occurrence)."""
    out = {}
    paths = {p.name: p for p in ROOT.glob("data/raw/PSI-2[01]_*/**/*Chamber Calculator*.xlsx")}
    gases = ["O2", "He", "CO2", "N2", "H2O", "C2H4", "CH4", "C3H8", "C4H10", "C2H6", "H2"]
    for path in sorted(paths.values()):
        sheet = openpyxl.load_workbook(path, read_only=True, data_only=True)["EventData"]
        for r in list(sheet.iter_rows(values_only=True))[4:]:
            if r[0] != "TP" or not r[2] or str(r[2]) in out:
                continue
            start = dict(zip(gases, [float(x or 0) for x in r[39:50]]))
            total = sum(start.values())
            out[str(r[2])] = {
                "ignite": text(r[1]).lower(), "fuel": text(r[23]),
                "p_start": first(r[18]), "p_end": first(r[19]),
                "o2": round(100 * start["O2"] / total, 2) if total else None,
                "co2": round(100 * start["CO2"] / total, 3) if total else None,
                "source": f"{rel(path)} (EventData)",
            }
    return out


# ---------------------------------------------------------------- one test

def timing(point: dict) -> dict:
    """Ignition, outcome and burn time from a timing file."""
    t = point["timing"]
    if not t:
        return {}
    ignition, extinct, off = (stamp(t.get(k)) for k in ["Ignition and retraction", "Extinction detected", "MFCs off"])
    reason = text(t.get("Reason")).lower()
    if not ignition:
        return {"outcome": "not run (aborted before ignition)", "notes": f"abort: {reason}" if reason else ""}
    end = extinct or off
    burn = (end - ignition).total_seconds() if end else None
    if extinct:
        outcome = "brief flame" if burn is not None and burn <= BRIEF_S else "self-extinguished"
    elif "temperature" in reason:
        outcome = "aborted (burner temperature limit)"
    elif "timeout" in reason:
        outcome = "aborted (flow timeout)"
    else:
        outcome = "flow terminated"
    return {"outcome": outcome, "burn_time_s": burn}


def number(run: dict, key: str) -> float | None:
    return first(run.get(key))


def row(psi_id: int, test_id: str, point: dict, day: dict, calc: dict | None) -> dict:
    run = point["run"]
    out = {"psi_id": f"PSI-{psi_id}", "test_id": test_id, "date": iso(day_of(test_id)),
           "fuel_type": "gas burner" if psi_id in (20, 23) else "gas jet", "geometry": GEOMETRY[psi_id]}
    notes = []
    bottle = day.get("Fuel Bottle", "")
    if calc and calc["fuel"]:  # the calculator names the bottle of each test point
        species = {"Ethylene": "C2H4", "Methane": "CH4", "Hydrogen": "H2", "Nitrogen": "N2", "Helium": "He"}
        names = [species.get(n.strip(), n.strip()) for n in calc["fuel"].split("(")[0].split("/")]
        shares = numbers_in(calc["fuel"])
        bottle = " + ".join(f"{s:g}% {n}" for s, n in zip(shares, names)) if shares else f"100% {names[0]}"
    material, bottle = fuel_of(bottle)
    out.update(material=material, material_family=material)
    notes.append(f"fuel bottle {bottle}")

    # Fuel concentration in the fuel stream (CLD, E-FIELD): mole fraction commanded by the script
    c0, c1 = number(run, "concentrationInitial"), number(run, "concentrationFinal")
    if c1 is not None:
        notes.append(f"fuel {c1 * 100:g} % in fuel stream" + (f" (ramped from {c0 * 100:g} %)" if c0 not in (None, c1) else ""))
    # Commanded flows
    air, mix = number(run, "velocityAirFinalMPerSec"), number(run, "velocityMixFinalMPerSec")
    if air is not None:
        out["flow_cm_s"] = round(air * 100, 2)
        out["flow_direction"] = "concurrent"
        if number(run, "velocityAirIgnitionMPerSec") not in (None, air):
            out["flow_steps_cm_s"] = f"{number(run, 'velocityAirIgnitionMPerSec') * 100:g} > {air * 100:g}"
    if mix is not None:
        notes.append(f"fuel jet {mix * 100:g} cm/s")
    fuel_slpm, n2_slpm = number(run, "fuelBottleTestFlowRateN2Slpm"), number(run, "nitrogenTestFlowRateN2Slpm")
    if fuel_slpm is not None:
        notes.append(f"burner flow: fuel bottle {fuel_slpm:g} slpm + diluent {n2_slpm or 0:g} slpm (N2-equivalent)")
    # Electric field (E-FIELD): mesh voltage swept between min and max
    vmin, vmax = number_signed(run, "efieldMinVoltage"), number_signed(run, "efieldMaxVoltage")
    if vmax is not None:
        notes.append(f"mesh voltage {vmin:g} to {vmax:g} V ({day.get('Mesh Polarity', '')} supply)")

    # Atmosphere
    if psi_id in (21, 22):
        out.update(o2_percent=21, diluent="N2")  # coflow of synthetic air 21/79 O2/N2 (data interpretation documents)
    if psi_id == 23:
        atmosphere = untypo(day.get("Atmosphere*", ""))
        levels = sorted({int(x) for x in re.findall(r"~(\d+)%", atmosphere)})
        out["diluent"] = "He" if "He" in atmosphere else "N2"
        if len(levels) == 1:
            out["o2_percent"] = levels[0]
        else:
            notes.append(f"atmosphere {atmosphere} (O2 level of each test not given)")
        out["pressure_atm"] = 1.0
        notes.append("~1 atm, pressure rises and O2 drops with vitiation during the day")
    if psi_id == 20:
        out["diluent"] = "N2"
        out["diameter_mm"] = day["burner_mm"]
    if calc:
        if psi_id == 20:
            out.update(o2_percent=calc["o2"], co2_percent=calc["co2"])
        if calc["p_start"]:
            out["pressure_atm"] = round(calc["p_start"] / PSIA_PER_ATM, 3)
            notes.append(f"chamber {calc['p_start']:g} > {calc['p_end']:g} psia")
    # Ignition and outcome
    timed = timing(point)
    out.update({k: v for k, v in timed.items() if k != "notes"})
    if timed.get("notes"):
        notes.append(timed["notes"])
    if calc and calc["ignite"] in ("yes", "no"):
        out["ignited"] = calc["ignite"]
        if calc["ignite"] == "no" and out.get("outcome") not in ("not run (aborted before ignition)",):
            out["outcome"] = "no sustained ignition" if timed.get("burn_time_s") else "no ignition"
            out["burn_time_s"] = None
    elif out.get("outcome") and not out["outcome"].startswith("not run"):
        out["ignited"] = "yes"
    if not point["files"]:
        notes.append(f"no downlinked files, listed in {point['listed']} only")

    out["notes"] = "; ".join(n for n in notes if n)
    sources = point["files"][:2] + ([calc["source"]] if calc else []) + ([point["sheet"]] if "sheet" in point else [])
    out["source"] = " | ".join(dict.fromkeys(sources))
    return out


def numbers_in(value: str) -> list[float]:
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", value)]


def number_signed(run: dict, key: str) -> float | None:
    found = re.search(r"-?\d*\.?\d+", run.get(key, ""))
    return float(found.group()) if found else None


# ---------------------------------------------------------------- campaigns

# Test points of CLD day 17319 that appear only on its scanned test sheets (none ignited, so no data
# was downlinked); their ignition and outcome are facts transcribed from the sheets (facts.csv).
CLD_17319_SHEETS = ("data/raw/PSI-21_CLD-Flame/Raw Data/Legacy/Methane, dilute (0-40%)/"
                    "17319A3 Video and Image Data/17319 test sheets.pdf")
CLD_17319_SHEETS_ONLY = ["17319A1", "17319A2", "17319D1", "17319D3", "17319D4", "17319E1", "17319E2", "17319H2"]

def new_tests() -> list[dict]:
    names = dict(INVESTIGATIONS)
    calc = calculator()
    rows = []
    for psi_id in PSI_IDS:
        table_days = days(psi_id)
        points = test_point_files(psi_id)
        if psi_id in (20, 21):  # test points the calculator lists but whose files were not downlinked
            for tp in calc:
                if day_of(tp) in table_days and tp not in points:
                    points[tp] = {"run": {}, "timing": {}, "files": [], "listed": "the chamber calculator"}
        if psi_id == 21:  # CLD day 17319 has no timing files; its test sheets list 8 more test points
            for tp in CLD_17319_SHEETS_ONLY:
                points[tp] = {"run": {}, "timing": {}, "files": [], "listed": "the scanned test sheets", "sheet": CLD_17319_SHEETS}
        for tp in sorted(points):
            day = table_days.get(day_of(tp))
            if day is None:
                print(f"  PSI-{psi_id}: {tp} has no test day in the experimental table, skipped")
                continue
            test = row(psi_id, tp, points[tp], day, calc.get(tp) if psi_id in (20, 21) else None)
            if psi_id == 22 and "gas-jet" in day.get("Test Type", ""):
                test["geometry"] = "gas jet flame (no coflow)"
            test["investigation"] = names[psi_id]
            rows.append(test)
    return rows


def updates() -> dict:
    """Nothing to update: tests.csv has no ACME rows yet."""
    return {}
