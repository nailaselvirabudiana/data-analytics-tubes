# data-analytics-tubes

Instruksi singkat untuk menyiapkan environment dan menjalankan skrip ekstraksi.

## Persyaratan
- Python 3.8+
- Paket: lihat `requirements.txt`

## Instalasi
Gunakan pip pada environment Python yang aktif:

```powershell
pip install -r requirements.txt
```

## Verifikasi
Pastikan `pandas` terpasang dan dapat diimpor:

```powershell
python -c "import pandas as pd; print(pd.__version__)"
```

## Menjalankan ekstraksi
Skrip ekstraksi utama ada di `scripts/extract_api.py`.

```powershell
python3 scripts/extract_api.py
```

Skrip ini memakai Open Data Jabar secara API-first:
1. mengambil dokumen OpenAPI dari `api-backend/static/doc/...`,
2. membaca endpoint data aktual dari dokumen tersebut,
3. mengambil seluruh record statistik dengan pagination `limit` dan `skip`,
4. menyimpan JSON dan CSV mentah ke `data/raw/`.

Dengan alur ini, ketika data di Open Data Jabar diperbarui, pipeline cukup dijalankan ulang tanpa download manual.

## Catatan VS Code
Jika VS Code menandai `pandas` kuning, pilih interpreter Python yang sama dengan yang Anda gunakan untuk menginstal paket: Command Palette → `Python: Select Interpreter`.

## Manifest & idempotensi
Setiap kali skrip dijalankan, script akan menyimpan versi mentah dengan timestamp di `data/raw/` dan menambahkan entri pada manifest: `data/manifest/ingest_manifest.csv`.
Kolom manifest: `ingest_time, logical_name, stored_filename, source_url, checksum, status, notes`.

Jika checksum JSON sudah ada di manifest, script akan melewatkan penyimpanan ulang dan mencatat status `skipped`.

## Orkestrasi
Contoh scaffold Prefect ada di `scripts/orchestrate_prefect.py`. Untuk penggunaan sederhana, Anda juga bisa menambahkan cron job yang menjalankan `python3 scripts/extract_api.py`.

## Preprocessing / Scrub OSEMN
Peran data preprocessing lead terutama berada di tahap **S - Scrub** pada kerangka OSEMN: membersihkan data, menangani missing value, standardisasi kolom dan tipe data, integrasi dataset, serta feature engineering.

Tahap **E - Explore** tetap dilakukan secara ringan untuk kebutuhan preprocessing, misalnya profiling missing value, duplikasi key, rentang tahun, dan validasi hasil cleaning. EDA analitis penuh seperti interpretasi tren utama, visualisasi insight, atau rekomendasi kebijakan biasanya menjadi area analyst/modeling lead setelah data bersih tersedia.

Skrip preprocessing utama:

```powershell
python3 scripts/preprocess_data.py
```

Secara default, output processed difilter ke periode analisis **2010-2024** sesuai scope obtain. Raw API tetap disimpan lengkap di `data/raw/`.

Jika perlu mengganti periode analisis:

```powershell
python3 scripts/preprocess_data.py --start-year 2010 --end-year 2024
```

Notebook preprocessing interaktif:

```text
notebooks/01_preprocessing_scrub.ipynb
```

Output utama:
- `data/processed/panel_kemiskinan_jabar_preprocessed.csv`
- `data/processed/feature_dictionary.csv`
- `data/processed/preprocess_manifest.csv`
- `reports/preprocessing/data_quality_summary.csv`
- `reports/preprocessing/preprocessing_quality_report.md`

Validasi processed data:

```powershell
python3 scripts/validate_processed_data.py
```

Output validasi:
- `reports/preprocessing/processed_validation_checks.csv`
- `reports/preprocessing/metric_coverage_by_year.csv`
- `reports/preprocessing/processed_validation_report.md`

Catatan: jika file raw yang tersedia masih berupa dokumentasi OpenAPI, bukan record statistik, skrip akan mencoba mengambil record aktual dari endpoint yang terdokumentasi. Untuk mode offline murni, jalankan:

```powershell
python3 scripts/preprocess_data.py --no-fetch-openapi
```
