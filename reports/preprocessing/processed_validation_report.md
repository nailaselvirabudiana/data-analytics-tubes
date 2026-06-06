# Processed Data Validation Report

Generated at: 2026-06-06T05:46:44.213970Z

## Verdict

- FAIL checks: 0
- WARN checks: 0
- PASS checks: 17

## Panel Summary

- Rows: 405
- Columns: 37
- Kabupaten/kota count: 27
- Year range: 2010-2024
- Latest scored year: 2024

## Checks

| check | status | value | expectation |
| --- | --- | --- | --- |
| required_columns_present | PASS | all present | All required dimension, key, and metric columns exist. |
| unique_kabupaten_kota_year_key | PASS | 0 | No duplicate kode_kabupaten_kota + tahun rows. |
| no_exact_duplicate_rows | PASS | 0 | No exact duplicate rows. |
| no_missing_key_values | PASS | 0 | No missing kode_kabupaten_kota or tahun. |
| no_missing_dimension_values | PASS | 0 | No missing geographic dimension values. |
| expected_region_count | PASS | 27 | Expected 27 kabupaten/kota in Jawa Barat panel. |
| year_range_available | PASS | 2010-2024 | Record the available year range; not all metrics must cover every year. |
| analysis_period_matches_scope | PASS | 2010-2024 | Processed panel should use the obtain-stage scope 2010-2024. |
| garis_kemiskinan_domain_range | PASS | 0 | Non-null metric values are inside expected domain range. |
| persentase_penduduk_miskin_domain_range | PASS | 0 | Non-null metric values are inside expected domain range. |
| indeks_keparahan_kemiskinan_domain_range | PASS | 0 | Non-null metric values are inside expected domain range. |
| indeks_pembangunan_manusia_domain_range | PASS | 0 | Non-null metric values are inside expected domain range. |
| tingkat_pengangguran_terbuka_domain_range | PASS | 0 | Non-null metric values are inside expected domain range. |
| no_zero_placeholders_remaining | PASS | {'garis_kemiskinan': 0, 'persentase_penduduk_miskin': 0, 'indeks_keparahan_kemiskinan': 0, 'indeks_pembangunan_manusia': 0, 'tingkat_pengangguran_terbuka': 0} | Source zero placeholders should be converted to missing values during preprocessing. |
| latest_scored_year_exists | PASS | 2024 | At least one year has complete vulnerability-score components. |
| score_only_when_components_complete | PASS | incomplete_with_score=0; complete_without_score=0 | Vulnerability score is populated only when all 4 risk components are available. |
| priority_rank_matches_score_availability | PASS | score_without_rank=0; rank_without_score=0 | Priority rank exists exactly when vulnerability score exists. |

## Metric Coverage By Year

| tahun | garis_kemiskinan | persentase_penduduk_miskin | indeks_keparahan_kemiskinan | indeks_pembangunan_manusia | tingkat_pengangguran_terbuka |
| --- | --- | --- | --- | --- | --- |
| 2010 | 26 | 26 | 26 | 26 | 26 |
| 2011 | 26 | 26 | 26 | 26 | 26 |
| 2012 | 26 | 26 | 26 | 26 | 26 |
| 2013 | 26 | 26 | 26 | 27 | 26 |
| 2014 | 26 | 26 | 26 | 27 | 26 |
| 2015 | 27 | 27 | 27 | 27 | 27 |
| 2016 | 27 | 27 | 27 | 27 | 0 |
| 2017 | 27 | 27 | 27 | 27 | 27 |
| 2018 | 27 | 27 | 27 | 27 | 27 |
| 2019 | 27 | 27 | 27 | 27 | 27 |
| 2020 | 27 | 27 | 27 | 27 | 27 |
| 2021 | 27 | 27 | 27 | 27 | 27 |
| 2022 | 27 | 27 | 27 | 27 | 27 |
| 2023 | 27 | 27 | 27 | 27 | 27 |
| 2024 | 27 | 27 | 27 | 27 | 27 |

## Interpretation Notes

- Missing metric values are acceptable when a source dataset does not cover that year.
- For intervention-priority analysis, use rows where `skor_kerentanan_sosial` is not missing.
- For latest complete priority analysis in the current data, use the latest scored year shown above.
