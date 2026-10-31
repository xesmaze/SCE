python3 - <<'PY'
from pathlib import Path

path = Path("sce/management.py")
source = path.read_text()

start = source.find("\ndef set_manager_parameters(")
end = source.find("\ndef set_manager_enabled(", start)

if start == -1 or end == -1:
    raise SystemExit("Helper functions not found. No changes made.")

# Find the end of the second helper function.
next_def = source.find("\ndef ", end + 1)
next_class = source.find("\nclass ", end + 1)
candidates = [p for p in (next_def, next_class) if p != -1]
helper_end = min(candidates) if candidates else -1

if helper_end == -1:
    raise SystemExit("Cannot safely locate helper boundary. No changes made.")

helpers = source[start:helper_end]
updated = source[:start] + source[helper_end:] + helpers + "\n"

compile(updated, str(path), "exec")
path.write_text(updated)
print("PASS: Helper functions moved after the module imports.")
PY