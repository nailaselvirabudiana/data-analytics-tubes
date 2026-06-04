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
python scripts/extract_api.py
```

## Catatan VS Code
Jika VS Code menandai `pandas` kuning, pilih interpreter Python yang sama dengan yang Anda gunakan untuk menginstal paket: Command Palette → `Python: Select Interpreter`.

## Manifest & idempotensi
Setiap kali skrip dijalankan, script akan menyimpan versi mentah dengan timestamp di `data/raw/` dan menambahkan entri pada manifest: `data/manifest/ingest_manifest.csv`.
Kolom manifest: `ingest_time, logical_name, stored_filename, source_url, checksum, status, notes`.

Jika checksum JSON sudah ada di manifest, script akan melewatkan penyimpanan ulang dan mencatat status `skipped`.

## Orkestrasi
Contoh scaffold Prefect ada di `scripts/orchestrate_prefect.py`. Untuk penggunaan sederhana, Anda juga bisa menambahkan cron job yang menjalankan `python scripts/extract_api.py`.
