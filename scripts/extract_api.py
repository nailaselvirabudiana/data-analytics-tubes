import csv
import hashlib
import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests


# Tentukan root direktori proyek agar relative path selalu konsisten
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"
MANIFEST_PATH = PROJECT_ROOT / "data" / "manifest" / "ingest_manifest.csv"
LOG_DIR = PROJECT_ROOT / "logs"

# 1. Pastikan folder arsitektur mentah tersedia sesuai standar tugas besar.
RAW_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logfile = LOG_DIR / "ingest.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(logfile, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

BASE_URL = "https://data.jabarprov.go.id"

if not MANIFEST_PATH.exists():
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as mf:
        writer = csv.writer(mf)
        writer.writerow(
            [
                "ingest_time",
                "logical_name",
                "stored_filename",
                "source_url",
                "checksum",
                "status",
                "notes",
            ]
        )


# 2. URL ini adalah dokumen OpenAPI dari Open Data Jabar.
# Script akan membaca dokumen ini untuk menemukan endpoint record data aktual.
api_docs = {
    "raw_garis_kemiskinan": f"{BASE_URL}/api-backend/static/doc/bps-od_20003_garis_kemiskinan_berdasarkan_kabupatenkota_v2.json",
    "raw_persentase_miskin": f"{BASE_URL}/api-backend/static/doc/bps-od_17058_persentase_penduduk_miskin__kabupatenkota.json",
    "raw_keparahan_kemiskinan": f"{BASE_URL}/api-backend/static/doc/bps-od_19998_indeks_keparahan_kemiskinan__kabupatenkota.json",
    "raw_ipm_sp2010": f"{BASE_URL}/api-backend/static/doc/bps-od_17045_indeks_pmbngnn_manusia_menggunakan_uhh_sp2010__kab.json",
    "raw_pengangguran_terbuka": f"{BASE_URL}/api-backend/static/doc/bps-od_17044_tingkat_pengangguran_terbuka__kabupatenkota.json",
}


def extract_records(payload: Any) -> List[Dict[str, Any]]:
    """Extract tabular records from common Open Data Jabar response shapes."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]

    for value in payload.values():
        if isinstance(value, list):
            rows = [row for row in value if isinstance(row, dict)]
            if rows:
                return rows

    return []


def resolve_data_endpoint(openapi_doc: Dict[str, Any]) -> str:
    """Resolve the collection endpoint from an OpenAPI document."""
    servers = openapi_doc.get("servers") or [{"url": "/api-backend/bigdata/bps/"}]
    server_url = servers[0].get("url", "/api-backend/bigdata/bps/")

    collection_paths = [
        path
        for path in openapi_doc.get("paths", {})
        if "{id}" not in path
    ]
    if not collection_paths:
        raise ValueError("Tidak menemukan collection path pada dokumen OpenAPI.")

    collection_path = sorted(collection_paths)[0]
    if server_url.startswith("http"):
        return server_url.rstrip("/") + "/" + collection_path.lstrip("/")

    return BASE_URL.rstrip("/") + "/" + server_url.strip("/") + "/" + collection_path.lstrip("/")


def fetch_all_records(session: requests.Session, endpoint: str, limit: int = 5000) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch all paginated records from an Open Data Jabar endpoint."""
    rows: List[Dict[str, Any]] = []
    skip = 0
    page_count = 0
    last_page_signature = None

    while True:
        params = {"limit": limit, "skip": skip}
        response = session.get(endpoint, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        batch = extract_records(payload)

        if not batch:
            break

        page_signature = hashlib.sha256(
            json.dumps(batch, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if page_signature == last_page_signature:
            raise RuntimeError(
                "API mengembalikan halaman yang sama berulang kali; pagination dihentikan untuk mencegah loop."
            )

        rows.extend(batch)
        page_count += 1
        logger.info("Fetched page %s from %s (%s total rows)", page_count, endpoint, len(rows))

        if len(batch) < limit:
            break

        last_page_signature = page_signature
        skip += len(batch)

    metadata = {
        "endpoint": endpoint,
        "limit": limit,
        "pages": page_count,
        "rows": len(rows),
    }
    return rows, metadata


def checksum_records(records: List[Dict[str, Any]]) -> str:
    raw_bytes = json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


def checksum_already_exists(checksum: str) -> Tuple[bool, str]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as mf:
        reader = csv.DictReader(mf)
        for row in reader:
            if row.get("checksum") == checksum and row.get("status") == "success":
                return True, row.get("stored_filename", "")
    return False, ""


def append_manifest(
    logical_name: str,
    stored_filename: str,
    source_url: str,
    checksum: str,
    status: str,
    notes: str,
) -> None:
    with MANIFEST_PATH.open("a", encoding="utf-8", newline="") as mf:
        writer = csv.writer(mf)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                logical_name,
                stored_filename,
                source_url,
                checksum,
                status,
                notes,
            ]
        )


def update_latest_copy(stored_json: Path, stored_csv: Path, logical_name: str) -> None:
    latest_json = RAW_DIR / f"{logical_name}.json"
    latest_csv = RAW_DIR / f"{logical_name}.csv"
    shutil.copy2(stored_json, latest_json)
    shutil.copy2(stored_csv, latest_csv)


def apply_retention(logical_name: str, keep_latest: int = 5) -> None:
    """Apply retention policy to archived versions.

    This will keep the `keep_latest` most recent timestamped versions in `data/archive`
    and remove older ones. The `data/raw` folder always keeps only the latest copies.
    """
    pattern = re.compile(rf"^{re.escape(logical_name)}_(\d{{8}}T\d{{6}}Z)\.(json|csv)$")
    versions: Dict[str, List[Path]] = {}

    for path in ARCHIVE_DIR.iterdir():
        match = pattern.match(path.name)
        if match:
            versions.setdefault(match.group(1), []).append(path)

    timestamps = sorted(versions.keys(), reverse=True)
    keep = set(timestamps[:keep_latest])

    for timestamp, paths in versions.items():
        if timestamp in keep:
            continue
        for path in paths:
            try:
                path.unlink()
                logger.info("Deleted old archived version: %s", path.name)
            except Exception:
                logger.warning("Failed to delete old archived version: %s", path.name)


def fetch_and_save(logical_name: str, doc_url: str) -> bool:
    logger.info("Memulai ekstraksi: %s", logical_name)

    try:
        session = requests.Session()

        doc_response = session.get(doc_url, timeout=60)
        doc_response.raise_for_status()
        openapi_doc = doc_response.json()

        data_endpoint = resolve_data_endpoint(openapi_doc)
        records, metadata = fetch_all_records(session, data_endpoint)

        if not records:
            raise RuntimeError(f"Tidak ada record data dari endpoint: {data_endpoint}")

        checksum = checksum_records(records)
        already, prev_file = checksum_already_exists(checksum)

        if already:
            logger.info("Skipped %s: checksum sudah pernah diingest (%s)", logical_name, prev_file)
            append_manifest(
                logical_name=logical_name,
                stored_filename=prev_file,
                source_url=data_endpoint,
                checksum=checksum,
                status="skipped",
                notes="duplicate_checksum",
            )
            return True

        ingest_time = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stored_base = f"{logical_name}_{ingest_time}"
        stored_json = ARCHIVE_DIR / f"{stored_base}.json"
        stored_csv = ARCHIVE_DIR / f"{stored_base}.csv"

        raw_payload = {
            "source_doc_url": doc_url,
            "source_data_url": data_endpoint,
            "ingest_time_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metadata": metadata,
            "data": records,
        }

        with stored_json.open("w", encoding="utf-8") as handle:
            json.dump(raw_payload, handle, ensure_ascii=False, indent=2)

        df = pd.json_normalize(records)
        df.to_csv(stored_csv, index=False)

        update_latest_copy(stored_json, stored_csv, logical_name)

        logger.info(
            "Sukses: %s rows tersimpan ke %s dan %s",
            len(df),
            stored_json,
            stored_csv,
        )

        append_manifest(
            logical_name=logical_name,
            stored_filename=stored_json.name,
            source_url=data_endpoint,
            checksum=checksum,
            status="success",
            notes=f"rows={len(df)};doc_url={doc_url}",
        )

        apply_retention(logical_name)
        return True

    except Exception as exc:
        logger.exception("Gagal mengekstrak %s. Error: %s", logical_name, exc)
        append_manifest(
            logical_name=logical_name,
            stored_filename="",
            source_url=doc_url,
            checksum="",
            status="failed",
            notes=str(exc),
        )
        return False


if __name__ == "__main__":
    print("=== Memulai Pipeline Ekstraksi Data dari API ===\n")
    failed = []
    for name, endpoint_doc in api_docs.items():
        ok = fetch_and_save(name, endpoint_doc)
        if not ok:
            failed.append(name)
    print("\n=== Ekstraksi Selesai ===")
    if failed:
        raise SystemExit(f"Ekstraksi gagal untuk: {', '.join(failed)}")
