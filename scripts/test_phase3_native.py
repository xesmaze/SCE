import json
import copy
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "template_models/Soy_Template_v2.0_APSIM2026.apsimx"
OUTDIR = ROOT / "phase3_native_test"
OUTDIR.mkdir(exist_ok=True)

model = json.loads(SOURCE.read_text())
simulation = next(x for x in model["Children"] if x["Name"] == "Simulation")

def find(node, name):
    if isinstance(node, dict):
        if node.get("Name") == name:
            return node
        for child in node.get("Children", []):
            result = find(child, name)
            if result is not None:
                return result
    return None

clock = find(simulation, "Clock")
clock["Start"] = "2001-01-01T00:00:00"
clock["End"] = "2001-12-31T00:00:00"

weather = find(simulation, "Weather")
weather["FileName"] = str((SOURCE.parent / "z_12.met").resolve())

sowing = find(simulation, "Sowing")
params = {p["Key"]: p for p in sowing["Parameters"]}

updates = {
    "SowDate": "12-apr",
    "CultivarName": "mid000",
    "Population": "40",
    "RowSpacing": "500",
    "SowingDepth": "30",
}

for key, value in updates.items():
    assert key in params, f"Missing sowing parameter: {key}"
    params[key]["Value"] = value

for manager_name in ["Fertilise at sowing", "Tillage on a fixed date"]:
    manager = find(simulation, manager_name)
    assert manager is not None
    manager["Enabled"] = False

target = OUTDIR / "SCE_Phase3_2001_mid000.apsimx"
assert not target.exists(), f"Model already exists: {target}"
target.write_text(json.dumps(model, indent=2))

apsim = (
    "/Applications/APSIM2026.10.8138.0.app/"
    "Contents/Resources/bin/Models"
)

subprocess.run([apsim, str(target)], check=True)

db = target.with_suffix(".db")
with sqlite3.connect(db) as conn:
    rows = conn.execute("SELECT COUNT(*) FROM Report").fetchone()[0]
    sowing_dates = conn.execute(
        "SELECT DISTINCT SimSowDate FROM Report "
        "WHERE SimSowDate IS NOT NULL AND SimSowDate != 'NA'"
    ).fetchall()

print("Report rows:", rows)
print("Simulated sowing dates:", sowing_dates)
print("Output model:", target)