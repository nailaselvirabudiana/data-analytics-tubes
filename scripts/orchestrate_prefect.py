"""
Minimal Prefect flow to run the extract pipeline.

This is a scaffold/template. Install `prefect` to use:

    pip install prefect

Run locally:

    prefect deployment build scripts/orchestrate_prefect.py:flow -n "extract" 
    prefect deployment apply orchestrate_prefect-extract-deployment.yaml

Or simply call `python scripts/extract_api.py` in a scheduled job.
"""
from prefect import flow, task
import subprocess


@task(retries=2)
def run_extraction():
    # call the extraction script; capture output
    result = subprocess.run(["python", "scripts/extract_api.py"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Extraction failed: {result.stderr}")
    return result.stdout


@flow(name="extract-pipeline")
def flow_main():
    out = run_extraction()
    print(out)


if __name__ == '__main__':
    flow_main()
