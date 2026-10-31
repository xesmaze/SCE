"""SCEpy command-line entry point."""
import runpy
import sys
from pathlib import Path

COMMANDS = {
    "run": "run_sce_integrated.py",
    "site": "prepare_site.py",
    "weather": "acquire_openmeteo_weather.py",
    "soil": "acquire_usda_horizons.py",
    "soil-stage": "apply_usda_soil.py",
    "characterize": "characterize_season.py",
    "batch": "characterize_batch.py",
    "wide": "export_wide.py",
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("SCEpy — Seasonal Characterization Engine")
        print("Usage: scepy COMMAND [options]")
        print("Commands: " + ", ".join(COMMANDS))
        print("Run 'scepy COMMAND --help' for options. APSIM is installed separately.")
        return 0
    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 2
    script = Path(__file__).resolve().parent / "_cli_tools" / COMMANDS[cmd]
    sys.argv = [str(script)] + sys.argv[2:]
    # Legacy helper imports in the integrated runner reside next to its script.
    sys.path.insert(0, str(script.parent))
    runpy.run_path(str(script), run_name="__main__")
    return 0
