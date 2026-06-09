# data-analytics-tubes

Poverty and social-vulnerability analytics for Jawa Barat, built on the OSEMN framework

## Requirements
- Python 3.13+
- Dependency manager: `uv`
- Dependencies are declared in `pyproject.toml` and locked in `uv.lock`

## Install uv
Install uv from Astral if it is not on your machine:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Setup
Sync the environment from the lockfile:

```bash
uv sync
```

## Verify
Check that pandas is installed and importable:

```bash
uv run python -c "import pandas as pd; print(pd.__version__)"
```

## Obtain
The main extraction script is `scripts/extract_api.py`:

```bash
uv run python scripts/extract_api.py
```

It uses Open Data Jabar in an API-first way:
- fetch the OpenAPI document from `api-backend/static/doc/`
- read the actual data endpoint from that document
- pull every statistical record with `limit` and `skip` pagination
- save raw JSON and CSV to `data/raw/`

When Open Data Jabar updates, rerun the pipeline with no manual download

## VS Code note
If VS Code marks `pandas` yellow, select the same Python interpreter you used to install the packages through Command Palette then `Python: Select Interpreter`

## Manifest and idempotency
Each run saves a timestamped raw version under `data/raw/` and appends an entry to the manifest `data/manifest/ingest_manifest.csv`
Manifest columns: `ingest_time, logical_name, stored_filename, source_url, checksum, status, notes`

When a JSON checksum already exists in the manifest, the script skips re-saving and records the status `skipped`

## Orchestration
A Prefect scaffold is in `scripts/orchestrate_prefect.py`
For simple use, add a cron job that runs `uv run python scripts/extract_api.py`

## Scrub
The preprocessing lead owns the S - Scrub stage: cleaning, missing-value handling, column and type standardization, dataset integration, and feature engineering

A light Explore runs here only for data quality, for example missing-value profiling, duplicate keys, year range, and cleaning checks; the full analytical Explore belongs to the analyst stage once the clean data is ready

Main preprocessing script:

```bash
uv run python scripts/preprocess_data.py
```

By default the processed output is filtered to the 2010-2024 analysis period from the obtain scope; the full raw API stays in `data/raw/`

To change the analysis period:

```bash
uv run python scripts/preprocess_data.py --start-year 2010 --end-year 2024
```

The interactive OSEMN notebook covering every stage is `notebooks/OSEMN.ipynb`
After `uv sync` the notebook runs without extra flags, both in an editor and headless:

```bash
uv run jupyter nbconvert --to notebook --execute notebooks/OSEMN.ipynb --output /tmp/OSEMN_run.ipynb
```

Main outputs:
- `data/processed/panel_kemiskinan_jabar_preprocessed.csv`
- `data/processed/feature_dictionary.csv`
- `data/processed/preprocess_manifest.csv`
- `reports/preprocessing/data_quality_summary.csv`

Validate the processed panel:

```bash
uv run python scripts/validate_processed_data.py
```

Validation outputs:
- `reports/preprocessing/processed_validation_checks.csv`
- `reports/preprocessing/metric_coverage_by_year.csv`

Note: when a raw file is still an OpenAPI document rather than statistical records, the script fetches the actual records from the documented endpoint
For a strictly offline run:

```bash
uv run python scripts/preprocess_data.py --no-fetch-openapi
```

## Explore and Model
The analyst and modeler owns the E - Explore and M - Model stages
Explore computes the numeric findings such as descriptive statistics, correlation, trend, and comparison, while chart rendering is handed to the visualization developer
Model clusters the regions, profiles the clusters, ranks feature importance, and builds the intervention priority matrix

The analysis unit is kabupaten/kota; the desa level in the title is not available from the obtained sources, so it stays out of scope

Exploratory analysis:

```bash
uv run python scripts/explore_analysis.py
```

Exploration outputs as CSV, with the interpretation in the notebook Explore section:
- `reports/exploration/descriptive_stats_latest.csv`
- `reports/exploration/correlation_matrix_latest.csv`
- `reports/exploration/poverty_trend_by_year.csv`
- `reports/exploration/region_change_summary.csv`
- `reports/exploration/kota_vs_kabupaten_latest.csv`
- `reports/exploration/top_bottom_regions_latest.csv`

Clustering model:

```bash
uv run python scripts/model_clustering.py
```

The default uses the latest fully scored snapshot year, `k=3`, and a 6-year trend window
Override when needed:

```bash
uv run python scripts/model_clustering.py --year 2024 --k 3 --k-max 6 --trend-window 6
```

Use `--k 0` to pick `k` automatically by silhouette

Modeling outputs as CSV, with the model summary, priority matrix, and limitations in the notebook Model and iNterpret sections:
- `data/processed/region_clusters_{year}.csv`
- `data/processed/cluster_model_manifest.csv`
- `reports/modeling/model_selection.csv`
- `reports/modeling/cluster_profiles.csv`
- `reports/modeling/feature_importance.csv`
- `reports/modeling/urban_rural_comparison.csv`
- `reports/modeling/priority_matrix.csv`

## Visualization Dashboard

The Streamlit dashboard renders the exploration and modeling outputs for decision support:

- summary KPIs and latest priority regions
- province and regional trends
- regional comparison and indicator correlation
- vulnerability clusters and intervention priority matrix
- data coverage and validation results

Run the dashboard from the repository root:

```bash
uv sync
uv run streamlit run dashboard/app.py
```

The dashboard reads the generated CSV files directly. Rerun the preprocessing, exploration, and
modeling scripts before the dashboard when the raw sources change.
