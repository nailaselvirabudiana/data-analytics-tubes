import requests
import pandas as pd
import os
import json
import hashlib
import csv
from datetime import datetime
import logging
from pathlib import Path
import re

# 1. Pastikan folder arsitektur mentah tersedia sesuai standar tugas besar
os.makedirs('data/raw', exist_ok=True)
os.makedirs('data/manifest', exist_ok=True)
os.makedirs('logs', exist_ok=True)

# Setup basic logging
logfile = Path('logs/ingest.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(logfile, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Manifest path
MANIFEST_PATH = Path('data/manifest/ingest_manifest.csv')
if not MANIFEST_PATH.exists():
    with MANIFEST_PATH.open('w', encoding='utf-8', newline='') as mf:
        writer = csv.writer(mf)
        writer.writerow(['ingest_time', 'logical_name', 'stored_filename', 'source_url', 'checksum', 'status', 'notes'])

# 2. Masukkan 5 URL API lengkap dari Open Data Jabar
base_url = "https://data.jabarprov.go.id"
api_endpoints = {
    "raw_garis_kemiskinan": f"{base_url}/api-backend/static/doc/bps-od_20003_garis_kemiskinan_berdasarkan_kabupatenkota_v2.json",
    "raw_persentase_miskin": f"{base_url}/api-backend/static/doc/bps-od_17058_persentase_penduduk_miskin__kabupatenkota.json",
    "raw_keparahan_kemiskinan": f"{base_url}/api-backend/static/doc/bps-od_19998_indeks_keparahan_kemiskinan__kabupatenkota.json",
    "raw_ipm_sp2010": f"{base_url}/api-backend/static/doc/bps-od_17045_indeks_pmbngnn_manusia_menggunakan_uhh_sp2010__kab.json",
    "raw_pengangguran_terbuka": f"{base_url}/api-backend/static/doc/bps-od_17044_tingkat_pengangguran_terbuka__kabupatenkota.json"
}

# 3. Fungsi ekstraksi dan penyimpanan
def fetch_and_save(filename, url):
    logger.info(f"Memulai ekstraksi: {filename}...")
    try:
        response = requests.get(url)
        response.raise_for_status()

        data_json = response.json()

        # compute checksum of the raw json bytes
        raw_bytes = json.dumps(data_json, ensure_ascii=False).encode('utf-8')
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        # check manifest for existing checksum (idempotency)
        already = False
        with MANIFEST_PATH.open('r', encoding='utf-8') as mf:
            reader = csv.DictReader(mf)
            for row in reader:
                if row.get('checksum') == checksum:
                    already = True
                    prev_file = row.get('stored_filename')
                    break

        ingest_time = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        stored_base = f"{filename}_{ingest_time}"
        stored_json = Path(f"data/raw/{stored_base}.json")
        stored_csv = Path(f"data/raw/{stored_base}.csv")

        if already:
            logger.info(f"Skipped {filename}: checksum already ingested (existing file: {prev_file})")
            with MANIFEST_PATH.open('a', encoding='utf-8', newline='') as mf:
                writer = csv.writer(mf)
                writer.writerow([datetime.utcnow().isoformat(), filename, prev_file, url, checksum, 'skipped', 'duplicate_checksum'])
            return

        # Simpan versi mentah JSON sebagai backup aslinya (versioned filename)
        with stored_json.open('w', encoding='utf-8') as f:
            json.dump(data_json, f, ensure_ascii=False, indent=2)

        # Helper: konversi berbagai struktur JSON ke DataFrame dengan aman
        def to_dataframe(obj):
            if isinstance(obj, list):
                try:
                    return pd.json_normalize(obj)
                except Exception:
                    return pd.DataFrame(obj)

            if isinstance(obj, dict):
                if 'data' in obj and isinstance(obj['data'], list):
                    return pd.json_normalize(obj['data'])

                for v in obj.values():
                    if isinstance(v, list):
                        try:
                            return pd.json_normalize(v)
                        except Exception:
                            return pd.DataFrame(v)

                try:
                    return pd.json_normalize(obj)
                except Exception:
                    return pd.DataFrame([obj])

            return pd.DataFrame([obj])

        df = to_dataframe(data_json)
        df.to_csv(stored_csv, index=False)

        # Update latest pointer (overwrite non-versioned files)
        latest_json = Path(f"data/raw/{filename}.json")
        latest_csv = Path(f"data/raw/{filename}.csv")
        try:
            stored_json.replace(latest_json)
            stored_csv.replace(latest_csv)
        except Exception:
            # fallback to copy if replace fails
            with stored_json.open('rb') as src, latest_json.open('wb') as dst:
                dst.write(src.read())
            with stored_csv.open('rb') as src, latest_csv.open('wb') as dst:
                dst.write(src.read())

        logger.info(f"✅ Sukses! Data tersimpan: {stored_json} dan {stored_csv} (latest updated)")

        # append manifest
        with MANIFEST_PATH.open('a', encoding='utf-8', newline='') as mf:
            writer = csv.writer(mf)
            writer.writerow([datetime.utcnow().isoformat(), filename, stored_json.name, url, checksum, 'success', ''])

        # Retention: keep only N latest versioned timestamps
        N = 5
        pattern = re.compile(rf"^{re.escape(filename)}_(\d{{8}}T\d{{6}}Z)\.(json|csv)$")
        versions = {}
        for p in Path('data/raw').iterdir():
            m = pattern.match(p.name)
            if m:
                ts = m.group(1)
                versions.setdefault(ts, []).append(p)

        timestamps = sorted(versions.keys(), reverse=True)
        to_keep = set(timestamps[:N])
        for ts, paths in versions.items():
            if ts not in to_keep:
                for p in paths:
                    try:
                        p.unlink()
                        logger.info(f"Deleted old version: {p.name}")
                    except Exception:
                        logger.warning(f"Failed to delete old version: {p.name}")
        
    except Exception as e:
        logger.exception(f"❌ Gagal mengekstrak {filename}. Error: {e}")
        with MANIFEST_PATH.open('a', encoding='utf-8', newline='') as mf:
            writer = csv.writer(mf)
            writer.writerow([datetime.utcnow().isoformat(), filename, '', url, '', 'failed', str(e)])

# 4. Jalankan Pipeline
if __name__ == "__main__":
    print("=== Memulai Pipeline Ekstraksi Data ===\n")
    for name, endpoint in api_endpoints.items():
        fetch_and_save(name, endpoint)
    print("\n=== Ekstraksi Selesai ===")