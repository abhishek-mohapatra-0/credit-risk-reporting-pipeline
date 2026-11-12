"""One command to rebuild everything: data -> checks -> SQL -> report."""
import subprocess
import sys

STEPS = [
    ["src/generate_data.py"],
    ["src/dq_checks.py"],
    ["src/build_report.py"],
]

for step in STEPS:
    print(f"\n>> {' '.join(step)}")
    subprocess.run([sys.executable, *step], check=True)
print("\nDone. Open reports/ for the Excel pack and CSV extracts.")
