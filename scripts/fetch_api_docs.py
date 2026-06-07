import requests
from pathlib import Path

API_DIR = Path("data/api")
API_DIR.mkdir(parents=True, exist_ok=True)

api_docs = {
    "raw_garis_kemiskinan": "https://data.jabarprov.go.id/api-backend/static/doc/bps-od_20003_garis_kemiskinan_berdasarkan_kabupatenkota_v2.json",
    "raw_persentase_miskin": "https://data.jabarprov.go.id/api-backend/static/doc/bps-od_17058_persentase_penduduk_miskin__kabupatenkota.json",
    "raw_keparahan_kemiskinan": "https://data.jabarprov.go.id/api-backend/static/doc/bps-od_19998_indeks_keparahan_kemiskinan__kabupatenkota.json",
    "raw_ipm_sp2010": "https://data.jabarprov.go.id/api-backend/static/doc/bps-od_17045_indeks_pmbngnn_manusia_menggunakan_uhh_sp2010__kab.json",
    "raw_pengangguran_terbuka": "https://data.jabarprov.go.id/api-backend/static/doc/bps-od_17044_tingkat_pengangguran_terbuka__kabupatenkota.json",
}


def fetch_all():
    # Download API docs locally
    for name, url in api_docs.items():
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            dest = API_DIR / f"{name}.json"
            with dest.open("w", encoding="utf-8") as fh:
                fh.write(resp.text)
            print(f"Saved {name} to {dest}")
        except Exception as e:
            print(f"Failed to fetch {name} from {url}: {e}")


if __name__ == "__main__":
    fetch_all()
