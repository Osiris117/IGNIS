#!/usr/bin/env python3
"""IGNIS — descargador de datos FIRMS reales para el archivo local (sin MAP_KEY).

Usa el servicio de **CSV masivos** de NASA FIRMS (bulk download), que es
público y NO requiere MAP_KEY. Los archivos se importan al archivo DuckDB local,
de modo que la demo funciona después **sin internet**.

Uso:
    python tools/fetch_firms_snapshot.py              # 7 días, global
    python tools/fetch_firms_snapshot.py --days 1     # últimas 24 h
    python tools/fetch_firms_snapshot.py --sources MODIS_SP VIIRS_SNPP_SP

Los CSV se guardan en `data/archive/inbox/firms_bulk/` y luego se importan.

Notas:
- Los nombres de archivo FIRMS incluyen el rango de fechas (p. ej.
  `MODIS_C6_1_Global_7d.csv`); los servicios `*_24h.csv` y `*_7d.csv` existen
  para MODIS C6.1 y Suomi-NPP VIIRS C2.
- Estos productos tienen ~3 h de latencia y cobertura global; son ideales para
  una demo offline. Para ventanas históricas largas o por región sigue usando
  la API con MAP_KEY (`import_firms_archive.py` acepta cualquier CSV de FIRMS).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "archive" / "inbox" / "firms_bulk"

SERVICES: dict[str, dict[str, str]] = {
    "MODIS_SP": {
        "url": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_{window}.csv",
        "file": "MODIS_C6_1_Global_{window}.csv",
    },
    "VIIRS_SNPP_SP": {
        "url": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_{window}.csv",
        "file": "SUOMI_VIIRS_C2_Global_{window}.csv",
    },
}

WINDOWS = {"1": "24h", "7": "7d"}


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "IGNIS-research/0.7"})
    print(f"[FIRMS] {url}")
    with urllib.request.urlopen(request, timeout=180) as response, open(dest, "wb") as handle:
        total = 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)
            total += len(chunk)
    print(f"        → {dest.name} ({total / 1e6:.1f} MB)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga e importa un snapshot FIRMS global (sin MAP_KEY).")
    parser.add_argument("--days", choices=sorted(WINDOWS), default="7", help="Ventana del servicio masivo (1 = 24 h, 7 = 7 días)")
    parser.add_argument("--sources", nargs="+", default=list(SERVICES), choices=sorted(SERVICES), help="Fuentes a descargar")
    parser.add_argument("--no-import", action="store_true", help="Solo descargar, no importar al archivo DuckDB")
    args = parser.parse_args()

    window = WINDOWS[args.days]
    started = time.time()
    files: list[tuple[Path, str]] = []
    for source in args.sources:
        service = SERVICES[source]
        dest = INBOX / service["file"].format(window=window)
        try:
            download(service["url"].format(window=window), dest)
            files.append((dest, source))
        except Exception as exc:  # red, 404 del servicio, etc.
            print(f"[FIRMS] ERROR descargando {source}: {exc}")

    if not files:
        print("[FIRMS] Nada descargado.")
        return 1

    if not args.no_import:
        for path, source in files:
            print(f"[IGNIS] Importando {path.name} como {source}…")
            subprocess.run([sys.executable, str(ROOT / "import_firms_archive.py"), str(path), "--source", source], check=False)

    print(f"\n[IGNIS] Snapshot listo en {time.time() - started:.1f}s · {len(files)} archivo(s) en {INBOX}")
    print("[IGNIS] Demo offline: abre IGNIS → TRACK LOCAL ARCHIVE · REAL NASA DATA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
