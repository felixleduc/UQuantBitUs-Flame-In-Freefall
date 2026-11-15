"""Per-test values for the Saffire samples, reduced from their sensor spreadsheets.

Saffire-II (9 samples) and Saffire-III (2 samples) have one workbook per sample with a 30 Hz
"Calibrated Data" sheet (O2, CO2, pressure, anemometers, 4 radiometers, 6 plume and 6 sample
thermocouples, igniter). Saffire-I only has the Cygnus telemetry workbook (Saffire rows every
30 s, Cygnus cabin pressure and smoke detectors every 10 s).

Each sample is reduced to: initial and final O2 and CO2, initial pressure and its rise, peak
radiometer rise after the igniter is off (flame heat flux), peak sample and plume thermocouple,
measured flow, flame duration (igniter on to last radiometer signal), and whether the flame
ended when the fan was stopped. Values without a TEST_FIELDS column go to `notes`.

    python -I readers.py   # writes new_tests.csv and updates.csv next to this file
"""

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
import unify_data as ud

HERE = Path(__file__).parent
PSI_PER_ATM, KPA_PER_PSI = 14.696, 6.895
RADIOMETERS = [f"Radiometer {i}" for i in range(1, 5)]
FLAME_MW_CM2 = 2.0  # radiometer rise above pre-ignition baseline taken as a flame (noise is about 0.5)

# Outcome of the samples whose experimental table only says "did not sustain" or nothing, read from
# the sensors: the silicone radiometer rise lasts only while the igniter is on (igniter glow); sample 2-2
# also heated the plume thermocouples by 40 C, so a flame briefly existed.
OUTCOMES = {
    ("PSI-99", "2-1"): ("no", "no ignition"),
    ("PSI-99", "2-2"): ("no", "brief flame"),
    ("PSI-99", "2-3"): ("no", "no ignition"),
    ("PSI-99", "2-4"): ("no", "no ignition"),
    ("PSI-100", "S1"): ("yes", "burned out"),  # radiometers back to baseline 4 min before the fan stopped
    ("PSI-100", "S2"): ("yes", "extinguished at low flow"),  # flame signal drops to zero as the fan stops
}


def sample_files() -> dict:
    files = {}
    for path in sorted(ud.folder(99).glob("Raw Data/**/SAFFIRE_II_S*/*.xlsx")):
        files[("PSI-99", f"2-{path.parent.name[-1]}")] = path
    for path in sorted(ud.folder(100).glob("Raw Data/**/S[12]/*.xlsx")):
        files[("PSI-100", path.parent.name)] = path
    return files


def calibrated(path: Path) -> pd.DataFrame:
    # calamine reads these 30 Hz sheets in seconds (openpyxl takes minutes); the second row holds units
    frame = pd.read_excel(path, sheet_name="Calibrated Data", skiprows=[1], engine="calamine")
    frame = frame.apply(pd.to_numeric, errors="coerce").dropna(subset=["Elapsed Time (s)"])
    return frame.rename(columns={"Elapsed Time (s)": "t"})


def reduce_sample(d: pd.DataFrame) -> dict:
    """Per-test values of one 30 Hz sample record."""
    t = d["t"]
    on = d[d["Igniter Power Enable"] == 1]
    t_on, t_off = on["t"].min(), on["t"].max()
    before = d[(t >= t_on - 10) & (t < t_on)]
    end = d[t >= t.max() - 10]
    rise = (d[RADIOMETERS] - before[RADIOMETERS].median()).max(axis=1).rolling(30, center=True).mean()
    after = t > t_off + 1
    sustained = bool((rise[t > t_off + 15] > FLAME_MW_CM2).any())
    flame_end = t[(rise > FLAME_MW_CM2) & (t > t_on)].max() if sustained else None
    flow = d["Anemometer 1"].rolling(30, center=True).mean()
    fan_off = t[(t > t_on) & (flow < 5)].min()
    sample_tc = d[[c for c in d.columns if "Sample Temp" in c]].max(axis=1)
    plume_tc = d[[c for c in d.columns if "Plume Temp" in c]].max(axis=1)
    burning = d[(t >= t_on) & (t <= (flame_end if flame_end else t_off))]
    return {
        "o2_start": before["O2"].median(), "o2_end": end["O2"].median(),
        "co2_start": before["CO2"].median(), "co2_end": end["CO2"].median(),
        "p_start": before["Ambient Pressure"].median(),
        "p_rise_kpa": (d.loc[t >= t_on, "Ambient Pressure"].max() - before["Ambient Pressure"].median()) * KPA_PER_PSI,
        "flow": burning[["Anemometer 1", "Anemometer 2"]].median().mean(),
        "rad_peak": rise[after].max(), "sample_tc": sample_tc[t >= t_on].max(),
        "plume_tc": plume_tc[t >= t_on].max(), "plume_start": plume_tc[t < t_on].median(),
        "igniter_s": t_off - t_on, "flame_s": (flame_end - t_on) if sustained else 0,
        "ends_at_fan_off": bool(sustained and pd.notna(fan_off) and abs(flame_end - fan_off) < 15),
    }


def note(m: dict) -> str:
    parts = [
        f"sensors: O2 {m['o2_start']:.2f} > {m['o2_end']:.2f} %",
        f"CO2 {m['co2_start']:.2f} > {m['co2_end']:.2f} %",
        f"pressure rise {m['p_rise_kpa']:.2f} kPa",
        f"measured flow {m['flow']:.1f} cm/s",
        f"igniter on {m['igniter_s']:.0f} s",
        f"peak radiometer rise after igniter {m['rad_peak']:.1f} mW/cm2",
        f"peak sample TC {m['sample_tc']:.0f} C",
        f"peak plume TC {m['plume_tc']:.0f} C (start {m['plume_start']:.0f} C)",
    ]
    if m["flame_s"]:
        parts.append(f"flame {m['flame_s']:.0f} s from ignition"
                     + (", ended when the fan was stopped" if m["ends_at_fan_off"] else ""))
    return "; ".join(parts)


# ---------------------------------------------------------------- Saffire-I (telemetry only)

def saffire1() -> dict:
    path = next(ud.folder(98).glob("Raw Data/**/*.xlsx"))
    saf = pd.read_excel(path, sheet_name="SaffireData").apply(pd.to_numeric, errors="coerce")
    cyg = pd.read_excel(path, sheet_name="CygnusData").apply(pd.to_numeric, errors="coerce")
    t = "Relative Time (s)"
    rads = [f"Radiometer{i}Value" for i in range(1, 5)]
    saf = saf[saf[rads[0]] > -1000]  # rows before the radiometers were powered hold -4000
    pressure = cyg[[t, "PCM Press (psi)"]].replace(0, float("nan")).dropna()
    smoke = cyg[[t, "FIZ 2 Smoke Detector Scatterometer (V)"]].replace(0, float("nan")).dropna()
    out = {}
    starts = {n: saf.loc[saf[f"Sample{n}IgniterI"] != saf[f"Sample{n}IgniterI"].iloc[0], t].min() for n in (1, 2)}
    for n in (1, 2):
        t_on, t_stop = starts[n], starts.get(n + 1, float("inf"))  # sample 1 ends where sample 2 starts
        saf_n = saf[saf[t] < t_stop]
        base = saf.loc[saf[t] < t_on, rads].tail(3).median()
        rise = (saf_n[rads] - base).max(axis=1)
        flame = saf_n.loc[(saf_n[t] >= t_on) & (rise > 5 * FLAME_MW_CM2), t]
        p0 = pressure.loc[pressure[t] <= t_on, "PCM Press (psi)"].iloc[-1]
        window = (pressure[t] >= t_on) & (pressure[t] <= t_on + 600)
        s_window = (smoke[t] >= t_on) & (smoke[t] <= t_on + 600)
        parts = [f"sensors (30 s telemetry): peak radiometer rise {rise[saf_n[t] >= t_on].max():.0f} mW/cm2",
                 f"Cygnus cabin pressure {p0:.3f} psia, rise {(pressure.loc[window, 'PCM Press (psi)'].max() - p0) * KPA_PER_PSI:.2f} kPa",
                 f"Cygnus FIZ 2 smoke scatterometer (smoke wire also fires before ignition) {smoke.loc[smoke[t] < t_on, smoke.columns[1]].iloc[-1]:.3f} > "
                 f"{smoke.loc[s_window, smoke.columns[1]].max():.2f} V"]
        if saf[t].max() - t_on < 300:
            parts.append(f"record ends {saf[t].max() - t_on:.0f} s after ignition")
        else:
            parts.append(f"radiometer signal for about {flame.max() - t_on:.0f} s")
        out[("PSI-98", f"S{n}")] = ({"pressure_atm": round(p0 / PSI_PER_ATM, 3)}, "; ".join(parts),
                                    str(path.relative_to(REPO)))
    return out


# ---------------------------------------------------------------- outputs

def new_tests() -> list[dict]:
    return []  # every Saffire sample is already a row of tests.csv


def updates() -> dict:
    current = ud.base_frame()
    notes = {(r.psi_id, r.test_id): r.notes for r in current.itertuples()}
    out, sources = {}, {}

    def add(key, values, extra, source):
        old = notes.get(key, "")
        values["notes"] = f"{old}; {extra}" if old else extra
        if key in OUTCOMES:
            values["ignited"], values["outcome"] = OUTCOMES[key]
        out[key], sources[key] = values, source

    for key, path in sample_files().items():
        m = reduce_sample(calibrated(path))
        values = {"co2_percent": round(m["co2_start"], 2), "pressure_atm": round(m["p_start"] / PSI_PER_ATM, 3)}
        if key[0] == "PSI-100":  # the Saffire-III table gives neither O2 nor burn time
            values["o2_percent"] = round(m["o2_start"], 2)
            values["burn_time_s"] = round(m["flame_s"])
        add(key, values, note(m), str(path.relative_to(REPO)))
    for key, (values, extra, source) in saffire1().items():
        add(key, values, extra, source)
    updates.sources = sources
    return out
