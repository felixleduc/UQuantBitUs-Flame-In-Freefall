"""Readers for the droplet combustion investigations FLEX (PSI-69), FLEX-2 (PSI-68) and CFI (PSI-39).

    new_tests()  FLEX-2 test points (none in tests.csv yet) and the CFI tests of the data summary
                 spreadsheet that the CFI experimental table leaves out
    updates()    values for FLEX and CFI tests already in tests.csv, read from their per-test files

Per-test files used:
    TestSheet.txt        conditions, D0, Dext, kavg, fiber, crew/analyst comments (FLEX, CFI)
    Summary.pdf          same values with more digits (pdftotext), CFI adds kcool and Dext cool
    <test point>.txt     test-point log: igniter times, radiometer and chamber pressure every second
    *_Mixture.txt        measured chamber gas composition before a series of test points
    CFI_DataSummary_Spreadsheet_Jan2021.xlsx   one row per CFI test (227 tests)
"""

import re
import statistics
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

import pandas as pd

import unify_data

from unify_data import ROOT, TEST_FIELDS, first, folder, numbers, text

PSI = 14.6959  # psia per atm
MMHG = 760.0


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read(path: Path) -> str:
    return path.read_text(encoding="latin-1")


def round_or_none(value, digits=3):
    return None if value is None else round(value, digits)


# ---------------------------------------------------------------- per-test file readers

def sheet(path: Path) -> dict:
    """A TestSheet.txt: 'label = value' or 'label: value' lines, then free-text COMMENTS."""
    content = read(path)
    head, _, comments = content.partition("COMMENTS:")
    out = {}
    for line in head.splitlines():
        match = re.match(r"\s*([A-Za-z][^:=]*?)\s*[:=]\s*(.*)$", line)
        if match and match[2].strip():
            out[" ".join(match[1].split())] = match[2].strip()
    out["comments"] = text(comments)
    return out


def summary(path: Path) -> dict:
    """Values printed on a Summary.pdf plot (pdftotext): P, mole fractions, D0, Dext, kavg..."""
    import subprocess
    content = subprocess.run(["pdftotext", "-raw", str(path), "-"], capture_output=True, text=True).stdout
    out = {}
    for key, pattern in [
        ("p_mmhg", r"P = ([\d.]+) mmHg"), ("o2", r"YO2 = ([\d.]+)"), ("n2", r"YN2 = ([\d.]+)"),
        ("co2", r"YCO2 = ([\d.]+)"), ("he", r"YHe = ([\d.]+)"), ("xe", r"YXe = ([\d.]+)"),
        ("d0", r"D0 = ([\d.]+) mm"), ("dext", r"Dext = ([\d.]+) mm"), ("kavg", r"kavg = ([\d.]+)"),
        ("kcool", r"kavg, cool = ([\d.]+)"), ("dext_cool", r"Dext, cool = ([\d.]+) mm"),
    ]:
        if match := re.search(pattern, content):
            out[key] = float(match[1])
    return out


def timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip()[:23], "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return None


def log(path: Path) -> tuple[dict, list[dict]]:
    """A test-point log: event times, then one row a second of radiometer, pressure and temperature."""
    events, rows = {}, []
    for line in read(path).splitlines():
        if re.match(r"\d{4}-\d\d-\d\d ", line):
            cells = line.split()
            t = timestamp(f"{cells[0]} {cells[1]}")
            try:
                rows.append({"t": t, "narrow": float(cells[4]), "wide": float(cells[6]),
                             "psia": float(cells[-2]), "degc": float(cells[-1])})
            except (ValueError, IndexError):
                pass
        elif match := re.match(r"([A-Za-z][^:\t]*):\t+(.*)$", line):
            events[match[1].strip()] = match[2].strip()
    return events, rows


def chamber(rows: list[dict], events: dict) -> dict:
    """Mean chamber pressure (atm) and temperature (C) over the burn."""
    on = timestamp(events.get("AS Burn to Completion/Igniter On", ""))
    during = [r for r in rows if on is None or r["t"] >= on] or rows
    if not during:
        return {}
    return {"pressure_atm": round(statistics.mean(r["psia"] for r in during) / PSI, 3),
            "temperature_c": round(statistics.mean(r["degc"] for r in during), 1)}


GASES = {"O2": "O2", "He": "He", "CO2": "CO2", "N2": "N2", "Xe": "Xe"}


def mixtures(*psi_ids: int) -> list[dict]:
    """Measured chamber gas composition (mole %) of each radiometer point, e.g. 'C055R01'."""
    out = []
    for path in sorted(p for i in psi_ids for p in folder(i).rglob("*_[Mm][Ii]xture.txt")):
        lines = [line for line in read(path).splitlines() if line.strip()]
        header = [h.strip() for h in lines[0].split(",")]
        values = dict(zip(header, [v.strip() for v in lines[1].split(",")]))
        code = re.search(r"([A-Z]\d{2,3}R\d\d)_M", path.name, re.I)[1]
        gases = {g: first(values.get(g)) or 0.0 for g in GASES}
        if sum(gases.values()) < 90:  # E216R01 lists 0.003 % O2 and 78.9 % CO2: columns shifted, not used
            print(f"  {path.name}: gas fractions add up to {sum(gases.values()):.1f} %, skipped")
            continue
        fuels = {h: first(values[h]) for h in header[header.index("H20") + 1:] if first(values.get(h))}
        date = pd.to_datetime(values.get("Date/Time", "").split()[0], errors="coerce")
        out.append({"code": code, "gases": gases, "fuel_vapor": fuels, "date": values.get("Date/Time", ""),
                    "year": date.year if not pd.isna(date) else None, "source": rel(path)})
    return out


def diluent(gases: dict) -> str:
    return "+".join(g for g in ["N2", "CO2", "He", "Xe"] if (gases.get(g) or 0) >= 1)


def comments_outcome(comments: str) -> str:
    """Hot flame / cool flame outcome from the analyst comments of a FLEX or CFI test."""
    low = comments.lower()
    if re.search(r"\bno ignition|did not ignite|failed to ignite|not ignite", low):
        return "no ignition"
    cool_sentences = [s for s in re.split(r"(?<=\.)\s", low) if re.search(r"cool[- ]flame", s)]
    no_cool = any(re.search(r"(no|without)( evidence of)?( a)? cool[- ]flame(?! extinction)|no cool flame or", s)
                  for s in cool_sentences)
    cool = cool_sentences and not no_cool
    unsure = all(re.search(r"likely|indicative|probabl|may |possibl|suggest|appears", s) for s in cool_sentences)
    if re.search(r"radiative(ly)? (extinction|extinguish)|extinguishes radiatively|radiatively extinguish", low):
        hot = "radiative extinction"
    elif re.search(r"diffusive(ly)? extinction|extinguishes diffusively", low):
        hot = "diffusive extinction"
    elif "disrupt" in low and not re.search(r"(not|no|without)( \w+)? disrupt", low):
        hot = "disruption"
    elif "extinction" in low or "extinguish" in low:
        hot = "extinction"
    else:
        hot = ""
    if cool:
        return f"{hot or 'extinction'}, then {'probable ' if unsure else ''}cool flame"
    return hot


# ---------------------------------------------------------------- current state

def current(psi_id: str) -> dict[str, dict]:
    frame = unify_data.base_frame()
    return {r["test_id"]: r for r in frame[frame.psi_id == psi_id].to_dict("records")}


def changed(old: str, new) -> bool:
    if new is None or new == "":
        return False
    try:
        return abs(float(old) - float(new)) > 1e-6
    except (TypeError, ValueError):
        return text(old) != text(new)


def keep_changes(test: dict, values: dict[str, tuple]) -> dict[str, tuple]:
    """Only the fields whose value differs from tests.csv; values are (value, source)."""
    return {f: (v, s) for f, (v, s) in values.items() if f in TEST_FIELDS and changed(test.get(f, ""), v)}


def join(*parts) -> str:
    return "; ".join(p for p in parts if p)


def mm(label: str, value) -> str:
    return f"{label} {value:g} mm" if value else ""


def rate(label: str, value) -> str:
    return f"{label} {value:g} mm2/s" if value else ""


# ---------------------------------------------------------------- FLEX (PSI-69)

def flex_summary(directory: Path, number: int) -> tuple[dict, str]:
    """The Summary.pdf of a FLEX test; the FLEX_NNN variant is the later (2013) analysis."""
    for name in [f"PSI-69_Raw Data_FLEX_{number:03d}_Summary.pdf", f"PSI-69_Raw Data_FLEX-{number:03d}_Summary.pdf"]:
        if (directory / name).exists():
            values = summary(directory / name)
            if values:
                return values, rel(directory / name)
    return {}, ""


def precise(summary_value, sheet_value):
    """The 3-digit Summary.pdf value when it rounds to the 2-digit test sheet value."""
    if summary_value is not None and (sheet_value is None or abs(summary_value - sheet_value) <= 0.01):
        return summary_value
    return sheet_value


def flex_outcome(from_comments: str, table_end: str) -> str:
    """The table's test end (extinction, disruption, completion) made specific by the comments."""
    hot, _, cool = from_comments.partition(", then ")
    if table_end == "completion":
        return "burned to completion"
    if table_end == "disruption":
        hot = "disruption"
    elif table_end == "extinction" and hot in ("", "disruption"):
        hot = "extinction"
    return f"{hot}, then {cool}" if cool and hot else hot


def flex() -> tuple[list[dict], dict]:
    """FLEX tests from their test sheets: updates for the tests of the table, new rows for the others."""
    tests = current("PSI-69")
    # the sheets are numbered FLEX-NNN, the table's test numbers drift from FLEX-269 on (sheet FLEX-275
    # is table test 269, both H15H101): match on the CIR test point id, kept in notes as "FLEX id"
    by_cir = {}
    for test_id, row in tests.items():
        if match := re.match(r"FLEX id (\S+);", row["notes"]):
            by_cir.setdefault(match[1], []).append(test_id)
    cabin_air = {p.name.split("_")[2]: text(read(p)) for p in (folder(69) / "Calibration").glob("*_Chamber_Gases.txt")}
    new, out = [], {}
    for path in sorted(folder(69).rglob("*_TestSheet.txt")):
        number = int(re.search(r"FLEX-(\d+)", path.name)[1])
        s, sheet_src = sheet(path), rel(path)
        pdf, pdf_src = flex_summary(path.parent, number)
        src = pdf_src or sheet_src
        # the Summary.pdf gives 3 digits; the earlier of the two summaries of FLEX-158 and 159 lists
        # another gas (0.16 O2, 0.25 CO2) than their test sheet (0.18, 0.15): keep the sheet then
        o2, co2, n2, he = (precise(pdf.get(k), first(s.get(f"{g} Mole Fraction")))
                           for k, g in [("o2", "O2"), ("co2", "CO2"), ("n2", "N2"), ("he", "He")])
        gases = {"N2": n2, "CO2": co2, "He": he}
        pressure = round(pdf["p_mmhg"] / MMHG, 3) if "p_mmhg" in pdf else first(s.get("Pressure (atm)"))
        dext = pdf.get("dext", first(s.get("Dext (mm)")) if "nan" not in s.get("Dext (mm)", "nan") else None)
        kavg = pdf.get("kavg", first(s.get("kavg (mm2/s)")))
        cir = s.get("CIR Test Number", "")
        fiber = s.get("Fiber", "").lower()
        ids = by_cir.get(cir, [])
        test_id = ids[0] if len(ids) == 1 else str(number) if str(number) in ids or not cir else None
        outcome = flex_outcome(comments_outcome(s["comments"]), tests.get(test_id, {}).get("outcome", ""))
        values = {
            "o2_percent": (round(o2 * 100, 2) if o2 is not None else None, src),
            "co2_percent": (round(co2 * 100, 2) if co2 is not None else None, src),
            "pressure_atm": (pressure, src),
            "diluent": (diluent({g: (v or 0) * 100 for g, v in gases.items()}), src),
            "diameter_mm": (pdf.get("d0", first(s.get("D0 (mm)"))), src),
            "outcome": (outcome, sheet_src),
            "notes": (join(f"FLEX id {cir}", mm("extinction diameter", dext), rate("burning rate", kavg),
                           {"yes": "fiber-supported", "no": "free-floating"}.get(fiber, ""),
                           f"chamber {s['Temperature (K)']} K" if s.get("Temperature (K)") else "",
                           cabin_air.get(cir, ""), f"comments: {s['comments']}" if s["comments"] else ""),
                      join(sheet_src, pdf_src)),
        }
        if outcome == "no ignition":
            values["ignited"] = ("no", sheet_src)
        if test_id in tests:
            out[("PSI-69", test_id)] = keep_changes(tests[test_id], values)
            continue
        date = re.sub(r"^\w+, ", "", s.get("Test Date", ""))
        new.append({"psi_id": "PSI-69", "investigation": "FLEX", "test_id": str(number),
                    "date": pd.to_datetime(date).strftime("%Y-%m-%d") if date else "",
                    "fuel_type": "droplet", "material": s.get("Fuel", ""), "material_family": s.get("Fuel", ""),
                    "geometry": "droplet", **{k: v for k, (v, _) in values.items()},
                    "ignited": values.get("ignited", ("yes" if dext or kavg else "", ""))[0],
                    "source": join(sheet_src, pdf_src)})
    return new, out


# ---------------------------------------------------------------- CFI (PSI-39)

CFI_SPREADSHEET = "Science Documents/PSI-39_Science Documents_CFI_DataSummary_Spreadsheet_Jan2021.xlsx"


def cfi_spreadsheet() -> tuple[dict[str, dict], str]:
    path = folder(39) / CFI_SPREADSHEET
    rows = {}
    for sheet_name in ["Master Sheet", "DATA", "Igniter", "Comments"]:
        frame = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
        frame.columns = [" ".join(str(c).split()) for c in frame.columns]
        for r in frame.to_dict("records"):
            number = text(r["Flex Number"])
            if number:
                rows.setdefault(number, {}).update({k: text(v) for k, v in r.items() if text(v)})
    return rows, rel(path)


def cfi_files() -> dict[str, dict[str, Path]]:
    """Per-test files of each CFI test, by Flex number (logs are matched through the CIR id)."""
    files = {}
    for path in folder(39).rglob("*FLEX-*"):
        if match := re.search(r"FLEX-(\d+)_(TestSheet\.txt|Summary\.pdf|Summary_prelim\.pdf)$", path.name):
            files.setdefault(match[1], {}).setdefault(match[2].split(".")[0], path)
    for path in folder(39).rglob("PSI-39_Raw Data_F*.txt"):
        if match := re.fullmatch(r"PSI-39_Raw Data_(F\d+[A-Z]\d+)\.txt", path.name):
            files.setdefault(match[1].upper(), {})["log"] = path
    return files


def cfi_test(number: str, r: dict, files: dict, spreadsheet: str) -> dict[str, tuple]:
    mine = files.get(number, {})
    pdf_path = mine.get("Summary") or mine.get("Summary_prelim")
    pdf = summary(pdf_path) if pdf_path else {}
    s = sheet(mine["TestSheet"]) if "TestSheet" in mine else {}
    cir = r.get("CIR", "")
    log_path = files.get(cir.upper(), {}).get("log")
    measured = chamber(*reversed(log(log_path))) if log_path else {}
    comments = r.get("Comments", "")
    d0 = pdf.get("d0") or first(r.get("D0 ( mm )"))
    dext_hot = pdf.get("dext") or first(r.get("Dext, hot ( mm )"))
    khot = pdf.get("kavg") or first(r.get("khot ( mm^2/s )"))
    kcool = pdf.get("kcool") or first(r.get("kcool ( mm^2/s )"))
    dext_cool = pdf.get("dext_cool") or first(r.get("Dext,cool ( mm )"))
    burn = first(r.get("HF Burn Time"))
    outcome = comments_outcome(comments)
    if outcome != "no ignition" and (kcool or dext_cool) and "cool flame" not in outcome:
        outcome = f"{outcome or 'extinction'}, then cool flame"
    if outcome != "no ignition" and not outcome and (dext_hot or burn):
        outcome = "extinction"
    # FLEX-1213 Summary.pdf and test sheet give 0.21 O2 where the spreadsheet and table give 0.17 like
    # the other tests of that day: the summary value is kept only when it agrees with the spreadsheet
    o2 = precise(pdf.get("o2"), first(r.get("Oxygen")))
    if outcome == "no ignition":  # FLEX-1212 lists an "HF burn time" though the comments say no ignition
        burn = None
    if pdf.get("p_mmhg"):
        pressure, p_src = round(pdf["p_mmhg"] / MMHG, 3), rel(pdf_path)
    elif measured:
        pressure, p_src = measured["pressure_atm"], rel(log_path)
    else:
        pressure, p_src = first(r.get("Pressure (atm)") or r.get("Pressure")), spreadsheet
    reignitions = first(r.get("Reignitions"))
    gases = {"N2": first(r.get("Nitrogen")) or 0, "He": first(r.get("Helium")) or 0}
    return {
        "date": (r.get("Test Date", "")[:10], spreadsheet),
        "fuel_type": ("droplet", spreadsheet), "material": (r.get("Fuel", ""), spreadsheet),
        "material_family": (r.get("Fuel", ""), spreadsheet), "geometry": ("droplet", spreadsheet),
        "diameter_mm": (d0, rel(pdf_path) if pdf.get("d0") else spreadsheet),
        "o2_percent": (round(o2 * 100, 2) if o2 is not None else None, rel(pdf_path) if o2 == pdf.get("o2") else spreadsheet),
        "pressure_atm": (pressure, p_src),
        "diluent": (diluent({g: v * 100 for g, v in gases.items()}), spreadsheet),
        "ignited": ("no" if outcome == "no ignition" else "yes" if burn or dext_hot or outcome else "", spreadsheet),
        "outcome": (outcome, spreadsheet),
        "burn_time_s": (burn, spreadsheet),
        "notes": (join(f"fiber-supported: {r['Fiber']}" if r.get("Fiber") else "", f"CIR id {cir}",
                       mm("hot flame extinction diameter", dext_hot), rate("hot flame burning rate", khot),
                       rate("cool flame burning rate", kcool), mm("cool flame extinction diameter", dext_cool),
                       f"reignitions {reignitions:g}" if reignitions else "",
                       f"chamber {measured['temperature_c']} C" if measured else
                       (f"chamber {s['Temperature (K)']} K" if s.get("Temperature (K)") else ""),
                       f"igniter {r.get('Ignition Power ( W )', '')} for {r.get('Ignition Time ( ms )', '')}"
                       if r.get("Ignition Power ( W )") else "",
                       f"comments: {comments}" if comments else ""),
                  join(spreadsheet, rel(pdf_path) if pdf_path else "", rel(log_path) if log_path else "")),
    }


def cfi() -> tuple[list[dict], dict]:
    tests = current("PSI-39")
    rows, spreadsheet = cfi_spreadsheet()
    files = cfi_files()
    new, updates = [], {}
    for number, r in rows.items():
        values = cfi_test(number, r, files, spreadsheet)
        if number in tests:
            updates[("PSI-39", number)] = keep_changes(tests[number], {k: v for k, v in values.items()
                                                                         if k not in ("date", "material", "material_family")})
        else:
            new.append({"psi_id": "PSI-39", "investigation": "CFI", "test_id": number,
                        **{k: v for k, (v, _) in values.items()}, "source": spreadsheet})
    return new, updates


# ---------------------------------------------------------------- FLEX-2 (PSI-68)

FLEX2_FUELS = {  # fuel of each folder of reduced-gravity test points
    "100% Octane": "Octane",
    "95% Propanol, 5% Glycerol": "Propanol 95% / Glycerol 5%",
    "Binary Array 2014 - Decane": "Decane",
    "Binary Array 2015 - Decane": "Decane",
    "Binary Array 2015 - Ethanol": "Ethanol",
    "Condensed Phase 2014 - Propanol80_Glycerol20": "Propanol 80% / Glycerol 20%",
}


def flex2() -> list[dict]:
    """One test per droplet test point (R points are radiometer/gas-fill points, LCTF are filter calibrations)."""
    gas = mixtures(68, 69)  # the CIR chamber is shared: FLEX gas fills can precede FLEX-2 points
    logs = {}
    for path in sorted(folder(68).rglob("*.txt")):
        code = re.fullmatch(r"(?:PSI-68_Raw Data_)?([A-Z]\d{3}[A-QS-Z]\d\d)\.txt", path.name)
        if not code:
            continue
        group = next((FLEX2_FUELS[p.name] for p in path.parents if p.name in FLEX2_FUELS), "")
        # a test point present in both Reduced Gravity and Legacy is read once, from Reduced Gravity
        if code[1] not in logs or group:
            logs[code[1]] = (path, group)
    rows = []
    for code, (path, fuel) in sorted(logs.items()):
        events, data = log(path)
        started = timestamp(events.get("AS Started", "") or events.get("AS Burn to Completion/Igniter On", ""))
        # gas of the radiometer point of the same series letter and day, same year first (some
        # mixture dates have a wrong year, e.g. D005R01 is dated 2014 for 2015 tests)
        same_day = sorted((m for m in gas if m["code"][:4] == code[:4]),
                          key=lambda m: (m["year"] != (started.year if started else None), "PSI-69" in m["source"], m["code"]))
        mix = same_day[0] if same_day else None
        measured = chamber(data, events)
        fiber = "fiber-supported" if events.get("AS Setup Fiber Deployed") else \
            "free-floating" if events.get("AS Stretch Completed") else ""
        g = mix["gases"] if mix else {}
        vapor = ", ".join(f"{k} {v:g} %" for k, v in mix["fuel_vapor"].items()) if mix else ""
        rows.append({
            "psi_id": "PSI-68", "investigation": "FLEX-2", "test_id": code,
            "date": started.strftime("%Y-%m-%d") if started else "",
            "fuel_type": "droplet", "material": fuel, "material_family": fuel, "geometry": "droplet",
            "o2_percent": g.get("O2"), "co2_percent": g.get("CO2"),
            "pressure_atm": measured.get("pressure_atm"), "diluent": diluent(g),
            "notes": join(fiber,
                          f"chamber gas measured {mix['date']} ({mix['code']})" if mix else "",
                          f"fuel vapor in chamber before test: {vapor}" if vapor else "",
                          f"chamber {measured['temperature_c']} C" if measured else "",
                          f"igniter {events.get('Igniter Wattage', '')} W for {events.get('Igniter On Time (milliseconds)', '').replace(',', '')} ms",
                          "fuel not given in the legacy folder" if not fuel else ""),
            "source": rel(path) + (f"; {mix['source']}" if mix else ""),
        })
    return rows


# ---------------------------------------------------------------- entry points

def _all() -> tuple[list[dict], dict]:
    new_flex, flex_updates = flex()
    new_cfi, cfi_updates = cfi()
    return new_flex + flex2() + new_cfi, {**flex_updates, **cfi_updates}


def new_tests() -> list[dict]:
    return _all()[0]


def updates() -> dict[tuple, dict]:
    return {key: {f: v for f, (v, _) in fields.items()} for key, fields in _all()[1].items()}
