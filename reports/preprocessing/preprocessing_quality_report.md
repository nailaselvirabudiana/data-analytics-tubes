# Preprocessing Quality Report

Generated at: 2026-06-06T07:53:08.407386Z

## Scope

This report covers the Scrub stage for poverty and social-vulnerability analytics in Jawa Barat.
The light exploration included here is limited to data-quality profiling and output validation.

## Output Files

- `data/processed/panel_kemiskinan_jabar_preprocessed.csv`
- `data/processed/feature_dictionary.csv`
- `data/processed/preprocess_manifest.csv`
- `reports/preprocessing/data_quality_summary.csv`

## Integrated Panel

- Rows: 405
- Kabupaten/kota count: 27
- Analysis year range: 2010 - 2024
- Latest year with complete intervention-priority score: 2024
- Duplicate kabupaten/kota-year keys: 0

## Source Quality Summary

| logical_name | source_mode | rows_raw | rows_clean | missing_metric_before_impute | invalid_zero_values | imputed_values | duplicate_key_rows | rows_dropped_missing_keys |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| raw_garis_kemiskinan | csv | 594 | 594 | 14 | 14 | 0 | 0 | 0 |
| raw_persentase_miskin | csv | 405 | 405 | 5 | 5 | 0 | 0 | 0 |
| raw_keparahan_kemiskinan | csv | 567 | 567 | 14 | 14 | 0 | 0 | 0 |
| raw_ipm_sp2010 | csv | 405 | 405 | 3 | 3 | 0 | 0 | 0 |
| raw_pengangguran_terbuka | csv | 424 | 424 | 0 | 0 | 0 | 0 | 0 |

## Latest Scored-Year Top Priority Preview

| tahun | peringkat_prioritas_intervensi | nama_kabupaten_kota | skor_kerentanan_sosial | prioritas_intervensi | persentase_penduduk_miskin | indeks_keparahan_kemiskinan | tingkat_pengangguran_terbuka | indeks_pembangunan_manusia |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 1 | KABUPATEN KUNINGAN | 1.2018 | sangat_tinggi | 11.88 | 0.53 | 7.78 | 71.26 |
| 2024 | 2 | KABUPATEN INDRAMAYU | 1.0761 | sangat_tinggi | 11.93 | 0.54 | 6.25 | 69.83 |
| 2024 | 3 | KABUPATEN CIANJUR | 0.7443 | sangat_tinggi | 10.14 | 0.41 | 5.99 | 67.24 |
| 2024 | 4 | KABUPATEN SUBANG | 0.6687 | sangat_tinggi | 9.49 | 0.46 | 6.73 | 71.36 |
| 2024 | 5 | KABUPATEN CIREBON | 0.6097 | sangat_tinggi | 11.0 | 0.36 | 6.74 | 71.44 |
| 2024 | 6 | KABUPATEN GARUT | 0.5188 | tinggi | 9.68 | 0.29 | 6.96 | 68.79 |
| 2024 | 7 | KABUPATEN MAJALENGKA | 0.4586 | tinggi | 10.82 | 0.45 | 4.01 | 69.74 |
| 2024 | 8 | KABUPATEN SUMEDANG | 0.3969 | tinggi | 9.1 | 0.45 | 6.16 | 73.73 |
| 2024 | 9 | KABUPATEN BANDUNG BARAT | 0.3696 | tinggi | 10.49 | 0.23 | 6.7 | 70.03 |
| 2024 | 10 | KABUPATEN PURWAKARTA | 0.3641 | tinggi | 8.41 | 0.35 | 7.34 | 72.65 |

## Preprocessing Notes

- Zero placeholders in source metrics are treated as missing because they usually represent unavailable historical records, especially for newer administrative regions.
- Missing metric values are imputed only for internal gaps with linear interpolation within each kabupaten/kota; leading/trailing structural missing values remain blank.
- Geographic names are standardized to uppercase to stabilize joins.
- The intervention priority score excludes garis_kemiskinan from the composite because it is better treated as economic context than direct vulnerability incidence.
- If `source_mode` is `openapi_fetch`, the raw CSV in `data/raw` was not statistical records and the script fetched records from the endpoint documented in the raw JSON.
