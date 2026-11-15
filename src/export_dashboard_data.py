"""Write the JSON files the dashboard reads, from data/processed/.

    dashboard/data/tests.json      solid-material tests (the materials the dashboard asks about)
    dashboard/data/findings.json   findings for whole investigations, with quote and source

Usage:
    uv run python src/export_dashboard_data.py
"""

import json
import re

import pandas as pd

from list_psi_files import ROOT

PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "dashboard" / "data"

# A flame put out by the crew (flow cut, nitrogen) was still burning on its own: it counts as sustained
SUSTAINED = {"burned", "burned out", "flow terminated", "extinguished at low flow", "extinguished by N2"}
NOT_SUSTAINED = {"no ignition", "brief flame", "self-extinguished", "blown off"}
TEST_COLUMNS = ["psi_id", "investigation", "test_id", "date", "material", "material_family", "geometry",
                "thickness_mm", "diameter_mm", "o2_percent", "pressure_atm", "flow_cm_s", "flow_direction",
                "outcome", "burn_time_s", "spread_rate_mm_s", "notes"]


# Finding types shown and filtered in the dashboard, first match wins: the context.csv field when it is
# specific, else words of the finding. "Test setup" collects facts about how the tests were run.
TYPES = [
    ("Test setup", r"^$", r"test points|ignitions in|typical burn|were used|before saffire|were chosen|glovebox|"
                          r"needs orbit|needed for|flushed|cleared for|combinations with"),
    ("Cool flames", r"cool_flame", r"cool flame"),
    ("Smoke and detection", r"detection|smoke", r"smoke|soot|particle|dust"),
    ("Suppression", r"suppression", r"suppress|extinguisher|nitrogen flood"),
    ("Material behavior", r"material_flammability", r"melting|smolder|droplets upstream|nomex|fabric keeps"),
    ("Extinction", r"extinction", r"extinction|extingu|quench|blowoff|blow-off|radiative|oscillat|lift"),
    ("Ignition", r"ignition", r"ignit"),
    ("Flame spread", r"^$", r"spread|thermally thick"),
    ("Ventilation and flow", r"^$", r"ventilation|cm/s|\bflows?\b"),
    ("Oxygen and pressure limits", r"min_o2|limit", r"\bo2\b|oxygen|pressure|flammab|dilut|% ch4|% h2"),
]


def finding_type(field: str, value: str) -> str:
    for name, fields, words in TYPES:
        if field != "finding" and re.search(fields, field):
            return name
    for name, _, words in TYPES:
        if re.search(words, value.lower()):
            return name
    return "Flame behavior"


# Unit of the number that opens a value, named in its context.csv field
UNITS = {"min_o2_percent": "% O2", "ignition_limit_o2_percent": "% O2", "extinction_flow_cm_s": "cm/s",
         "extinction_temperature_k": "K", "extinction_mass_flux_g_m2_s": "g/m2-s"}


def with_unit(field: str, value: str) -> str:
    """'17.5 (PMMA rods...)' becomes '17.5 % O2 (PMMA rods...)'."""
    unit = UNITS.get(field)
    if not unit or unit in value[:24]:
        return value
    return re.sub(r"^([\d.]+(?: to [\d.]+)?(?: ± [\d.]+)?)", rf"\1 {unit}", value, count=1)


def records(frame: pd.DataFrame) -> list[dict]:
    """Rows as dicts without empty cells, so the JSON stays small and optional fields stay absent."""
    return [{k: v for k, v in row.items() if pd.notna(v) and v != ""} for row in frame.to_dict("records")]


def main() -> None:
    tests = pd.read_csv(PROCESSED / "tests.csv", low_memory=False)
    solids = tests[tests.fuel_type == "solid"][TEST_COLUMNS].copy()
    solids["sustained"] = solids.outcome.map(lambda o: True if o in SUSTAINED else False if o in NOT_SUSTAINED else None)

    context = pd.read_csv(PROCESSED / "context.csv", dtype=str, keep_default_na=False)
    findings = context[context.test_id == ""].drop(columns="test_id")
    investigations = pd.read_csv(PROCESSED / "investigations.csv", dtype=str, keep_default_na=False)
    findings = findings.merge(investigations[["psi_id", "acronym", "group", "url"]], on="psi_id", how="left")
    findings["type"] = [finding_type(f, v) for f, v in zip(findings.field, findings.value)]
    findings["value"] = [with_unit(f, v) for f, v in zip(findings.field, findings.value)]
    findings = findings.drop_duplicates(["value", "quote"])  # Saffire I to III share one status paper

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in [("tests.json", records(solids)), ("findings.json", records(findings))]:
        (OUT / name).write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
