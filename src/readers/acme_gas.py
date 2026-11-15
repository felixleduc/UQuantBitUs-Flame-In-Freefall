"""ACME gaseous spherical flames (PSI-10 Flame-Design, PSI-159 CFI-G): per-test-point files.

Each test point has a script log `<id>_TP.txt` (timestamps of ignition, extinction detected,
flows off, abort reason) and a definition `as run<id>.txt` or `<id>.txt` (commanded flows in slpm,
igniter settings). The experimental tables already give composition and pressure; these files
add whether the flame lit, how it ended and how long it burned.
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

import unify_data as u

PSI = {10: "Flame-Design", 159: "CFI-G"}
FOLDER_FUEL = [("ethylene", "C2H4"), ("propane", "propane"), ("n-butane", "n-butane"), ("ethane", "ethane")]


def stamps(path: Path) -> dict:
    """Script log: {'Test Point': '19189K1', 'Ignition and retraction': datetime | None, ...}."""
    out = {}
    for line in path.read_text(errors="replace").splitlines():
        key, sep, value = line.partition(":")
        if not sep or key.startswith(("Camera", "=")):
            continue
        value = value.strip()
        try:
            out[key.strip()] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            out[key.strip()] = None if value == "***" else value
    return out


def definition(path: Path) -> dict:
    """Test point definition: {'fuelTestFlow1Slpm': 0.1, ...} as floats where numeric."""
    out = {}
    for item in path.read_text(errors="replace").split(","):
        key, sep, value = item.strip().partition(":")
        if sep:
            out[key.strip()] = u.first(value) if re.fullmatch(r"-?[\d.]+", value.strip()) else value.strip()
    return out


def test_points(psi_id: int) -> dict[str, dict]:
    """Every test point of an investigation: {'21256K1': {'tp': Path, 'def': Path, 'fuel', 'kind'}}."""
    points = {}
    for path in sorted((u.folder(psi_id) / "Raw Data").rglob("*.txt")):
        rel = str(path.relative_to(u.ROOT))
        fuel, kind = kind_of(path)
        if path.name.endswith("_TP.txt"):
            name = stamps(path).get("Test Point") or ""
            test_id = re.sub(r"\s", "", name) or re.search(r"(\d{5}\w+)_TP", path.name).group(1)
            points.setdefault(test_id, {}).update(tp=path, fuel=fuel, kind=kind)
        else:
            test_id = re.search(r"(\d{5}\w+)\.txt$", path.name).group(1)
            entry = points.setdefault(test_id, {"fuel": fuel, "kind": kind})
            if "as run" in path.name or "def" not in entry:  # 'as run' wins over a plain definition
                entry["def"] = path
    return points


def from_log(log: dict) -> dict:
    """Ignition, outcome and burn time from a script log."""
    lit = log.get("Ignition and retraction")
    out, off = log.get("Extinction detected"), log.get("MFCs off")
    reason = (log.get("Reason") or "").lower()
    # Checked against the CFI-G table (which gives ignition, ending and burn time from video):
    # the log cannot tell a failed ignition (extinction is 'detected' then too), its extinction
    # time lags the flame-out by about 15 s, but 'MFCs off' gives the burn time of a
    # flow-terminated flame within 1 to 2 s, and extinction before flows off means self-extinction
    # in 154 of 165 lit tests.
    if lit is None:  # 10 such logs belong to tests the table shows burning: log incomplete
        return {}
    if "temperature" in reason:
        return {"outcome": "flow terminated", "burn_time_s": (off - lit).total_seconds() if off else None,
                "notes": "flows stopped by the burner temperature limit"}
    if out and (off is None or out <= off):
        return {"outcome": "self-extinguished",
                "notes": f"extinction detected {(out - lit).total_seconds():g} s after the ignition command"}
    if off:
        return {"outcome": "flow terminated", "burn_time_s": (off - lit).total_seconds()}
    return {}


PSIA = 14.696  # psia per atm


def calculator(psi_id: int) -> dict[str, dict]:
    """ACME Chamber Calculator 'EventData': one row per test point with the operations team's
    ignition call, measured chamber pressure before and after, and the computed start mixture."""
    out = {}
    for path in sorted(u.folder(psi_id).rglob("*Chamber Calculator*.xlsx")):
        sheet = pd.read_excel(path, sheet_name="EventData", header=None)
        for _, r in sheet[sheet[0] == "TP"].iterrows():
            test_id = u.text(r[2])
            # columns 39 to 49: start mixture in standard litres (O2, He, CO2, N2, H2O, fuels, H2)
            o2, co2 = u.first(r[39]) or 0, u.first(r[41]) or 0
            total = sum(u.first(r[c]) or 0 for c in range(39, 50))
            p0, p1 = u.first(r[18]), u.first(r[19])
            out[test_id] = {
                "ignite": u.text(r[1]).lower(),
                "o2": round(o2 / total * 100, 2) if total else None,
                "co2": round(co2 / total * 100, 3) if total else None,
                "p": round((p0 + p1) / 2 / PSIA, 3) if p0 and p1 else None,
                "p_range": f"{p0}-{p1} psia" if p0 and p1 else "",
                "fuel": u.text(r[23]), "date": str(r[12])[:10],
                "source": f"{path.relative_to(u.ROOT)} (EventData)",
            }
    return out


def per_test(psi_id: int) -> dict[str, dict]:
    """Values read from the per-test files, keyed by test point id without spaces."""
    calc = calculator(psi_id)
    rows = {}
    for test_id, p in test_points(psi_id).items():
        row, sources = {}, []
        if "tp" in p:
            log = stamps(p["tp"])
            row.update(from_log(log))
            sources.append(str(p["tp"].relative_to(u.ROOT)))
        if "def" in p:
            d = definition(p["def"])
            flows = {k: d.get(v) for k, *vs in [("fuel", "fuelTestFlow1Slpm", "fuelBottleTestFlowRateN2Slpm"),
                                                ("oxidizer", "oxidizerTestFlow1Slpm"),
                                                ("N2", "nitrogenTestFlow1Slpm", "nitrogenTestFlowRateN2Slpm")]
                     for v in vs if isinstance(d.get(v), float)}
            if flows:
                row["flows"] = "commanded " + ", ".join(f"{k} {v:g}" for k, v in flows.items() if v) + " slpm"
            sources.append(str(p["def"].relative_to(u.ROOT)))
        if c := calc.get(test_id):
            if c["ignite"] in ("yes", "no"):
                row["ignited"] = c["ignite"]  # the operations call beats the script log
            row.update(o2_calc=c["o2"], co2_percent=c["co2"], pressure_atm=c["p"], p_range=c["p_range"])
            sources.append(c["source"])
        if row.get("ignited") == "no":
            row.update(outcome="no ignition", burn_time_s=0)
            row.pop("notes", None)
        if "tp" in p and isinstance(log.get("Script start"), datetime):
            row["date"] = log["Script start"].strftime("%Y-%m-%d")
        rows[test_id] = {**row, "fuel": p["fuel"], "kind": p["kind"], "sources": sources}
    for test_id, c in calc.items():  # test points known only from the calculator (MFCA ones are calibrations)
        if test_id not in rows and re.fullmatch(r"\d{5}[A-Z]\d+", test_id):
            fuel = {"Ethylene": "C2H4", "Butane": "n-butane"}.get(c["fuel"], c["fuel"].lower())
            rows[test_id] = {"ignited": c["ignite"], "co2_percent": c["co2"], "pressure_atm": c["p"],
                             "o2_calc": c["o2"], "fuel": fuel, "date": c["date"],
                             # a normal flame burns in an O2 atmosphere, an inverse one in fuel
                             "kind": "normal" if (c["o2"] or 0) > 5 else "inverse",
                             **({"outcome": "no ignition", "burn_time_s": 0} if c["ignite"] == "no" else {}),
                             "sources": [c["source"]]}
    return rows


def current(psi_id: int) -> pd.DataFrame:
    tests = u.base_frame()
    tests = tests[tests.psi_id == f"PSI-{psi_id}"].copy()
    tests["key"] = tests.test_id.str.replace(" ", "")
    return tests.set_index("key")


def notes_for(row: dict) -> str:
    return "; ".join(x for x in [row.get("notes"), row.get("flows")] if x)


UPDATABLE = ["ignited", "outcome", "burn_time_s", "co2_percent", "pressure_atm"]


def updates() -> dict[tuple[str, str], dict]:
    """Fill empty cells of the tests already listed; table values are kept (they come from video)."""
    out = {}
    for psi_id in PSI:
        tests = current(psi_id)
        for key, row in per_test(psi_id).items():
            if key not in tests.index:
                continue
            have = tests.loc[key]
            if "no" in (have["ignited"], row.get("ignited")):  # the log timings mean nothing then
                row = {**row, "outcome": "no ignition", "burn_time_s": 0, "notes": ""}
            change = {f: row[f] for f in UPDATABLE if row.get(f) not in (None, "") and have[f] == ""}
            # CFI-G gives an approximate pressure in bar; the calculator measured it at start and end
            if psi_id == 159 and row.get("pressure_atm"):
                change["pressure_atm"] = row["pressure_atm"]
            if extra := notes_for(row):
                change["notes"] = "; ".join(x for x in [have["notes"], extra] if x)
            if change:
                change["source"] = "; ".join(row["sources"])
                out[(f"PSI-{psi_id}", have["test_id"])] = change
    return out


def kind_of(path: Path) -> tuple[str, str]:
    rel = str(path)
    return next(f for k, f in FOLDER_FUEL if k in rel), "inverse" if "inverse" in rel else "normal"


def new_tests() -> list[dict]:
    """Test points with a script log, a calculator line or a daily-notes ignition call, but no table row."""
    rows = []
    for psi_id, name in PSI.items():
        tests, notes = current(psi_id), daily_notes(psi_id)
        found = per_test(psi_id)
        for key, n in notes.items():  # failed ignitions noted by the PI with no other file
            if key not in found and n["ignited"]:
                found[key] = {"ignited": n["ignited"], "outcome": n["outcome"], "fuel": n["fuel"],
                              "kind": n["kind"], **({"burn_time_s": 0} if n["ignited"] == "no" else {}),
                              "sources": [n["file"]]}
        for key, row in found.items():
            evidence = any(s.endswith("_TP.txt") or "Calculator" in s or "flow traces" in s for s in row["sources"])
            if key in tests.index or not evidence:  # a definition alone does not show the test ran
                continue
            rows.append({
                "psi_id": f"PSI-{psi_id}", "investigation": name, "test_id": key, "date": row.get("date", ""),
                "fuel_type": "gas jet", "material": row["fuel"], "material_family": row["fuel"],
                "geometry": f"{row['kind']} spherical flame",
                # chamber O2 is the ambient only for normal flames (fuel into the chamber gas)
                "o2_percent": row.get("o2_calc") if row["kind"] == "normal" else None,
                "co2_percent": row.get("co2_percent"), "pressure_atm": row.get("pressure_atm"),
                **{f: row.get(f) for f in ["ignited", "outcome", "burn_time_s"]},
                "notes": notes_for(row), "source": "; ".join(row["sources"]),
            })
    return rows


# ---------------------------------------------------------------- daily notes (flow traces PDFs)

HEADLINE = re.compile(r"Test (\d{5} ?[A-Z]+\d+(?:_\d)?)(?: \([^)]*\))? [\u2013-] (.{0,160})")  # \u2013: the notes use a dash
STATUS = [  # first match wins
    (r"abort", "", "not run (aborted)"),
    (r"no (apparent |sustained )?(ignition|flame)|failed ignition|ignition unsuccessful|unsuccessful ignition"
     r"|not sustained|only flash|igniter didn", "no", "no ignition"),
    (r"unsustained ignition|momentary|quickly extinguished", "yes", "brief flame"),
    (r"sustained (ignition|flame)|successful (test|ignition)", "yes", ""),
]


def pdf_pages(path: Path) -> list[str]:
    raw = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout
    return [" ".join(p.split()) for p in raw.split("\f")]


def daily_notes(psi_id: int) -> dict[str, dict]:
    """The PI's headline for each test in the daily notes ('Test 21256H4 (...) - unsustained
    ignition, ...'), read as ignition and outcome. First mention wins (pages repeat on continuation)."""
    out = {}
    for path in sorted(u.folder(psi_id).rglob("*flow traces*.pdf")):
        fuel, kind = kind_of(path)
        for page, content in enumerate(pdf_pages(path), 1):
            for m in HEADLINE.finditer(content):
                key = m.group(1).replace(" ", "")
                # the first clause is the status; later ones cite other tests ('repeat of the aborted B2')
                status = re.split(r",| run with", m.group(2))[0]
                hit = next(((ig, oc) for p, ig, oc in STATUS if re.search(p, status, re.I)), None)
                if hit and key not in out:
                    out[key] = {"ignited": hit[0], "outcome": hit[1], "fuel": fuel, "kind": kind,
                                # the status after the dash (the test id is in test_id)
                                "quote": m.group(2).split(", run")[0].rstrip(" ,"),
                                "file": str(path.relative_to(u.ROOT)), "page": page}
    return out


def note_facts(merged: dict[tuple[str, str], dict]) -> list[dict]:
    """Daily-notes ignition and outcome, kept only where they add to or correct the merged values."""
    facts = []
    for psi_id in PSI:
        tests = current(psi_id)
        for key, n in daily_notes(psi_id).items():
            test_id = tests.loc[key, "test_id"] if key in tests.index else key
            have = merged.get((f"PSI-{psi_id}", test_id))
            if have is None:  # aborted before gas flow: no test
                continue
            fix = {"ignited": n["ignited"], "outcome": n["outcome"]}
            if n["ignited"] == "no":
                fix["burn_time_s"] = 0
            for field, value in fix.items():
                if value != "" and u.text(have.get(field)).removesuffix(".0") != str(value):
                    facts.append({"psi_id": f"PSI-{psi_id}", "test_id": test_id, "field": field, "value": value,
                                  "quote": n["quote"], "file": n["file"], "page": n["page"]})
    return facts


def merged_view(upd, new) -> dict:
    view = {}
    for psi_id in PSI:
        for _, r in current(psi_id).iterrows():
            view[(r.psi_id, r.test_id)] = dict(r)
    for k, v in upd.items():
        view[k].update(v)
    for r in new:
        view[(r["psi_id"], r["test_id"])] = r
    return view
