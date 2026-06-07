# Prefect scaffold for extraction

from prefect import flow, task
import subprocess
import sys


@task(retries=2)
def run_extraction():
    # Run extraction, capture output
    result = subprocess.run([sys.executable, "scripts/extract_api.py"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Extraction failed: {result.stderr}")
    return result.stdout


@flow(name="extract-pipeline")
def flow_main():
    out = run_extraction()
    print(out)


if __name__ == '__main__':
    flow_main()
