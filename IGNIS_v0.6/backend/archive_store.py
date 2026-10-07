from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import threading
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

try:
    import duckdb
except ImportError:  # Allows the rest of IGNIS to boot in a degraded mode.
    duckdb = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = ROOT / "data" / "archive"
INBOX_DIR = ARCHIVE_DIR / "inbox"
PARQUET_DIR = ARCHIVE_DIR / "parquet"
DB_PATH = ARCHIVE_DIR / "ignis.duckdb"

ARCHIVE_SOURCES = {
    "MODIS_SP": "MODIS · Standard Processing",
    "VIIRS_SNPP_SP": "VIIRS · Suomi-NPP Standard Processing",
    "VIIRS_NOAA20_SP": "VIIRS · NOAA-20 Standard Processing",
    "VIIRS_NOAA21_ARCHIVE": "VIIRS · NOAA-21 Archive",
}


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _family(source: str) -> str:
    return "MODIS" if source.startswith("MODIS") else "VIIRS" if source.startswith("VIIRS") else "OTHER"


def _calendar_level(score: float) -> str:
    if score >= 80:
        return "extreme"
    if score >= 60:
        return "very-high"
    if score >= 40:
        return "high"
    if score >= 20:
        return "moderate"
    return "low"


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 1.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return max(ordered[0], 1.0)
    idx = (len(ordered) - 1) * q
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return max(ordered[lo], 1.0)
    value = ordered[lo] * (hi - idx) + ordered[hi] * (idx - lo)
    return max(value, 1.0)


def parse_area(area: str) -> tuple[float, float, float, float]:
    parts = area.split(",")
    if len(parts) != 4:
        raise ValueError("area must be west,south,east,north")
    west, south, east, north = map(float, parts)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("invalid archive area coordinates")
    return west, south, east, north


@dataclass
class ImportResult:
    file: str
    source: str
    status: str
    rows_seen: int
    rows_inserted: int
    sha256: str
    message: str = ""


class ArchiveStore:
    """Local analytical store for historical FIRMS observations.

    DuckDB is the canonical local database. A compact monthly-grid Parquet snapshot is
    refreshed after imports so the same archive can also be inspected with other tools.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        PARQUET_DIR.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self):
        if duckdb is None:
            raise RuntimeError("DuckDB is not installed. Run the IGNIS launcher to install IGNIS dependencies.")
        return duckdb.connect(str(self.db_path))

    def ensure_schema(self) -> None:
        if duckdb is None:
            return
        with self._lock, self.connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS fire_observations (
                    event_key UBIGINT PRIMARY KEY,
                    source VARCHAR NOT NULL,
                    family VARCHAR NOT NULL,
                    latitude DOUBLE NOT NULL,
                    longitude DOUBLE NOT NULL,
                    acq_date DATE NOT NULL,
                    acq_time VARCHAR,
                    frp DOUBLE,
                    confidence DOUBLE,
                    brightness DOUBLE,
                    satellite VARCHAR,
                    instrument VARCHAR,
                    daynight VARCHAR,
                    origin_file VARCHAR,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS archive_imports (
                    sha256 VARCHAR PRIMARY KEY,
                    origin_file VARCHAR NOT NULL,
                    source VARCHAR NOT NULL,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rows_seen BIGINT,
                    rows_inserted BIGINT,
                    status VARCHAR,
                    message VARCHAR
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS monthly_grid (
                    source VARCHAR,
                    family VARCHAR,
                    year INTEGER,
                    month INTEGER,
                    grid_lat DOUBLE,
                    grid_lon DOUBLE,
                    detections BIGINT,
                    total_frp DOUBLE,
                    mean_frp DOUBLE,
                    max_frp DOUBLE
                );
                """
            )

    def _headers(self, path: Path) -> set[str]:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration:
                return set()
        return {h.strip().lower() for h in header if h.strip()}

    def _file_hash(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _column_expr(self, headers: set[str], names: Iterable[str], default: str = "NULL") -> str:
        for name in names:
            if name.lower() in headers:
                escaped = name.replace('"', '""')
                return f'"{escaped}"'
        return default

    def import_csv(self, path: Path, source: str) -> ImportResult:
        path = path.resolve()
        if source not in ARCHIVE_SOURCES:
            raise ValueError(f"Unsupported archive source: {source}")
        if path.suffix.lower() not in {".csv", ".txt"}:
            raise ValueError("Archive importer accepts CSV/TXT files")
        headers = self._headers(path)
        required = {"latitude", "longitude", "acq_date"}
        missing = required - headers
        if missing:
            raise ValueError(f"Missing FIRMS columns: {', '.join(sorted(missing))}")

        digest = self._file_hash(path)
        with self._lock, self.connect() as con:
            existing = con.execute("SELECT status, rows_inserted FROM archive_imports WHERE sha256 = ?", [digest]).fetchone()
            if existing:
                return ImportResult(path.name, source, "duplicate", 0, int(existing[1] or 0), digest, "This exact file was already imported.")

            lat = self._column_expr(headers, ["latitude"])
            lon = self._column_expr(headers, ["longitude"])
            acq_date = self._column_expr(headers, ["acq_date"])
            acq_time = self._column_expr(headers, ["acq_time"], "''")
            frp = self._column_expr(headers, ["frp"], "'0'")
            conf = self._column_expr(headers, ["confidence"], "''")
            brightness = self._column_expr(headers, ["bright_ti4", "brightness", "bright_t31", "bright_ti5"], "NULL")
            satellite = self._column_expr(headers, ["satellite"], "''")
            instrument = self._column_expr(headers, ["instrument"], "''")
            daynight = self._column_expr(headers, ["daynight"], "''")

            path_sql = _sql_literal(str(path))
            source_sql = _sql_literal(source)
            family_sql = _sql_literal(_family(source))
            origin_sql = _sql_literal(path.name)
            count_before = con.execute("SELECT count(*) FROM fire_observations").fetchone()[0]
            rows_seen = con.execute(f"SELECT count(*) FROM read_csv_auto({path_sql}, header=true, all_varchar=true, ignore_errors=true)").fetchone()[0]

            sql = f"""
            INSERT OR IGNORE INTO fire_observations
            WITH raw AS (
                SELECT * FROM read_csv_auto({path_sql}, header=true, all_varchar=true, ignore_errors=true)
            ), norm AS (
                SELECT
                    {source_sql}::VARCHAR AS source,
                    {family_sql}::VARCHAR AS family,
                    TRY_CAST({lat} AS DOUBLE) AS latitude,
                    TRY_CAST({lon} AS DOUBLE) AS longitude,
                    TRY_CAST({acq_date} AS DATE) AS acq_date,
                    LPAD(COALESCE(CAST({acq_time} AS VARCHAR), ''), 4, '0') AS acq_time,
                    COALESCE(TRY_CAST({frp} AS DOUBLE), 0.0) AS frp,
                    CASE lower(trim(COALESCE(CAST({conf} AS VARCHAR), '')))
                        WHEN 'l' THEN 30.0 WHEN 'low' THEN 30.0
                        WHEN 'n' THEN 65.0 WHEN 'nominal' THEN 65.0 WHEN 'medium' THEN 65.0
                        WHEN 'h' THEN 95.0 WHEN 'high' THEN 95.0
                        ELSE COALESCE(TRY_CAST({conf} AS DOUBLE), 0.0)
                    END AS confidence,
                    TRY_CAST({brightness} AS DOUBLE) AS brightness,
                    COALESCE(CAST({satellite} AS VARCHAR), '') AS satellite,
                    COALESCE(CAST({instrument} AS VARCHAR), '') AS instrument,
                    COALESCE(CAST({daynight} AS VARCHAR), '') AS daynight
                FROM raw
            ), prepared AS (
                SELECT
                    hash(concat_ws('|', source, CAST(latitude AS VARCHAR), CAST(longitude AS VARCHAR),
                        CAST(acq_date AS VARCHAR), acq_time, CAST(frp AS VARCHAR), satellite)) AS event_key,
                    source, family, latitude, longitude, acq_date, acq_time, frp,
                    greatest(0.0, least(100.0, confidence)) AS confidence,
                    brightness, satellite, instrument, daynight,
                    {origin_sql}::VARCHAR AS origin_file,
                    CURRENT_TIMESTAMP AS ingested_at
                FROM norm
                WHERE latitude BETWEEN -90 AND 90
                  AND longitude BETWEEN -180 AND 180
                  AND acq_date IS NOT NULL
            )
            SELECT * FROM prepared;
            """
            try:
                con.execute(sql)
                count_after = con.execute("SELECT count(*) FROM fire_observations").fetchone()[0]
                inserted = int(count_after - count_before)
                con.execute(
                    "INSERT INTO archive_imports VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, 'ok', ?)",
                    [digest, path.name, source, int(rows_seen), inserted, "Imported into local historical store"],
                )
            except Exception as exc:
                con.execute(
                    "INSERT OR REPLACE INTO archive_imports VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, 0, 'error', ?)",
                    [digest, path.name, source, int(rows_seen), str(exc)[:1000]],
                )
                raise

        return ImportResult(path.name, source, "ok", int(rows_seen), inserted, digest)

    def import_zip(self, path: Path, source: str) -> list[ImportResult]:
        results: list[ImportResult] = []
        work = ARCHIVE_DIR / "_zip_work"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(path) as zf:
                members = [m for m in zf.infolist() if not m.is_dir() and Path(m.filename).suffix.lower() in {".csv", ".txt"}]
                if not members:
                    raise ValueError("ZIP does not contain a CSV/TXT FIRMS file")
                for idx, member in enumerate(members):
                    safe = Path(member.filename).name
                    temp_path = work / f"{idx:03d}_{safe}"
                    with zf.open(member) as src, temp_path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    results.append(self.import_csv(temp_path, source))
        finally:
            shutil.rmtree(work, ignore_errors=True)
        self.refresh_aggregates()
        return results

    def import_path(self, path: Path, source: str) -> list[ImportResult]:
        if path.suffix.lower() == ".zip":
            return self.import_zip(path, source)
        result = self.import_csv(path, source)
        self.refresh_aggregates()
        return [result]

    def refresh_aggregates(self) -> None:
        with self._lock, self.connect() as con:
            con.execute("DELETE FROM monthly_grid")
            con.execute(
                """
                INSERT INTO monthly_grid
                SELECT
                    source,
                    family,
                    year(acq_date)::INTEGER AS year,
                    month(acq_date)::INTEGER AS month,
                    floor(latitude * 2.0) / 2.0 + 0.25 AS grid_lat,
                    floor(longitude * 2.0) / 2.0 + 0.25 AS grid_lon,
                    count(*)::BIGINT AS detections,
                    sum(frp)::DOUBLE AS total_frp,
                    avg(frp)::DOUBLE AS mean_frp,
                    max(frp)::DOUBLE AS max_frp
                FROM fire_observations
                GROUP BY ALL
                """
            )
            target = PARQUET_DIR / "monthly_grid.parquet"
            if target.exists():
                target.unlink()
            target_sql = _sql_literal(str(target))
            con.execute(f"COPY monthly_grid TO {target_sql} (FORMAT PARQUET, COMPRESSION ZSTD)")

    def status(self) -> dict[str, Any]:
        if duckdb is None:
            return {
                "ready": False, "engine_available": False, "observations": 0, "imports": 0,
                "min_date": None, "max_date": None, "database_bytes": 0, "parquet_bytes": 0, "sources": [],
                "error": "DuckDB dependency is not installed."
            }
        with self._lock, self.connect() as con:
            total, min_date, max_date = con.execute(
                "SELECT count(*), min(acq_date), max(acq_date) FROM fire_observations"
            ).fetchone()
            imports = con.execute("SELECT count(*) FROM archive_imports WHERE status = 'ok'").fetchone()[0]
            source_rows = con.execute(
                "SELECT source, count(*), min(acq_date), max(acq_date) FROM fire_observations GROUP BY source ORDER BY source"
            ).fetchall()
        return {
            "ready": bool(total),
            "engine_available": True,
            "db_path": str(self.db_path.relative_to(ROOT)),
            "observations": int(total or 0),
            "imports": int(imports or 0),
            "min_date": min_date.isoformat() if min_date else None,
            "max_date": max_date.isoformat() if max_date else None,
            "database_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            "parquet_bytes": (PARQUET_DIR / "monthly_grid.parquet").stat().st_size if (PARQUET_DIR / "monthly_grid.parquet").exists() else 0,
            "sources": [
                {"id": r[0], "label": ARCHIVE_SOURCES.get(r[0], r[0]), "observations": int(r[1]),
                 "min_date": r[2].isoformat() if r[2] else None, "max_date": r[3].isoformat() if r[3] else None}
                for r in source_rows
            ],
        }

    def _source_filter(self, sources: list[str] | None) -> tuple[str, list[Any]]:
        if not sources:
            return "", []
        good = [x for x in sources if x in ARCHIVE_SOURCES]
        if not good:
            raise ValueError("No supported local archive sources selected")
        placeholders = ",".join("?" for _ in good)
        return f" AND source IN ({placeholders})", good

    def calendar(self, area: str, start_year: int, end_year: int, sources: list[str] | None = None) -> dict[str, Any]:
        west, south, east, north = parse_area(area)
        today = date.today()
        end_year = min(end_year, today.year)
        if start_year > end_year:
            raise ValueError("start_year must not be after end_year")
        source_clause, source_args = self._source_filter(sources)
        start = date(start_year, 1, 1)
        end = date(end_year + 1, 1, 1) if end_year < 9999 else date(end_year, 12, 31)
        sql = f"""
            SELECT year(acq_date)::INTEGER AS year, month(acq_date)::INTEGER AS month,
                   count(*)::BIGINT AS detections,
                   sum(frp)::DOUBLE AS total_frp,
                   avg(frp)::DOUBLE AS mean_frp,
                   max(frp)::DOUBLE AS max_frp,
                   count(DISTINCT acq_date)::INTEGER AS active_days
            FROM fire_observations
            WHERE longitude >= ? AND longitude <= ? AND latitude >= ? AND latitude <= ?
              AND acq_date >= ? AND acq_date < ? {source_clause}
            GROUP BY 1,2 ORDER BY 1,2
        """
        args: list[Any] = [west, east, south, north, start, end, *source_args]
        with self._lock, self.connect() as con:
            records = con.execute(sql, args).fetchall()
        items = [
            {"year": int(r[0]), "month": int(r[1]), "detections": int(r[2]), "total_frp": round(float(r[3] or 0), 2),
             "frp_mean": round(float(r[4] or 0), 2), "frp_max": round(float(r[5] or 0), 2), "active_days": int(r[6] or 0)}
            for r in records
        ]
        counts = [float(x["detections"]) for x in items]
        total_frps = [float(x["total_frp"]) for x in items]
        p95_count = _percentile(counts, 0.95)
        p95_frp = _percentile(total_frps, 0.95)
        for item in items:
            score = 100.0 * (0.68 * min(1.0, item["detections"] / p95_count) + 0.32 * min(1.0, item["total_frp"] / p95_frp))
            item["score"] = round(score, 1)
            item["level"] = _calendar_level(score)
            item["available"] = True

        lookup = {(x["year"], x["month"]): x for x in items}
        rows: list[dict[str, Any]] = []
        for year in range(start_year, end_year + 1):
            months: list[dict[str, Any]] = []
            for month in range(1, 13):
                if year == today.year and month > today.month:
                    months.append({"month": month, "available": False, "score": None, "level": "future"})
                    continue
                item = lookup.get((year, month))
                if item:
                    months.append({k: v for k, v in item.items() if k != "year"})
                else:
                    months.append({"month": month, "available": True, "score": 0.0, "level": "low", "detections": 0, "total_frp": 0.0, "frp_mean": 0.0, "frp_max": 0.0, "active_days": 0})
            rows.append({"year": year, "months": months})
        return {
            "mode": "local-archive-calendar",
            "area": area,
            "start_year": start_year,
            "end_year": end_year,
            "sources": sources or [],
            "rows": rows,
            "sampling_note": "Complete local monthly totals from imported FIRMS archive observations. Scores are normalized within the selected period/AOI.",
        }

    def fires(self, area: str, start_date: date, days: int, sources: list[str] | None = None, max_points_per_day: int = 1600) -> list[dict[str, Any]]:
        west, south, east, north = parse_area(area)
        end_date = start_date + timedelta(days=days)
        source_clause, source_args = self._source_filter(sources)
        sql = f"""
            WITH ranked AS (
                SELECT source, family, latitude, longitude, acq_date, acq_time, frp, confidence,
                       brightness, satellite, instrument, daynight,
                       row_number() OVER (PARTITION BY acq_date ORDER BY hash(event_key)) AS rn
                FROM fire_observations
                WHERE longitude >= ? AND longitude <= ? AND latitude >= ? AND latitude <= ?
                  AND acq_date >= ? AND acq_date < ? {source_clause}
            )
            SELECT source, family, latitude, longitude, acq_date, acq_time, frp, confidence,
                   brightness, satellite, instrument, daynight
            FROM ranked
            WHERE rn <= ?
            ORDER BY acq_date, acq_time
        """
        args: list[Any] = [west, east, south, north, start_date, end_date, *source_args, max_points_per_day]
        with self._lock, self.connect() as con:
            records = con.execute(sql, args).fetchall()
        out: list[dict[str, Any]] = []
        for r in records:
            frp = float(r[6] or 0.0)
            confidence = float(r[7] or 0.0)
            severity_score = min(100.0, max(0.0, 0.60 * min(frp / 120.0, 1.0) * 100 + 0.40 * confidence))
            severity = "critical" if severity_score >= 72 else "high" if severity_score >= 45 else "moderate"
            out.append({
                "source": r[0], "family": r[1], "lat": round(float(r[2]), 6), "lon": round(float(r[3]), 6),
                "date": r[4].isoformat(), "time": r[5] or "", "frp": round(frp, 2), "confidence": round(confidence, 1),
                "brightness": float(r[8]) if r[8] is not None else None, "satellite": r[9] or "", "instrument": r[10] or "",
                "daynight": r[11] or "", "severity_score": round(severity_score, 1), "severity": severity,
            })
        return out

    def monthly_anomaly(self, area: str, target_year: int, target_month: int, years: int = 10, source: str = "MODIS_SP") -> dict[str, Any]:
        if source not in ARCHIVE_SOURCES:
            raise ValueError("Unsupported baseline source")
        west, south, east, north = parse_area(area)
        start_year = max(1900, target_year - years)
        with self._lock, self.connect() as con:
            rows = con.execute(
                """
                SELECT year(acq_date)::INTEGER AS year, count(*)::BIGINT AS detections, sum(frp)::DOUBLE AS total_frp
                FROM fire_observations
                WHERE source = ? AND longitude >= ? AND longitude <= ? AND latitude >= ? AND latitude <= ?
                  AND month(acq_date) = ? AND year(acq_date) BETWEEN ? AND ?
                GROUP BY 1 ORDER BY 1
                """,
                [source, west, east, south, north, target_month, start_year, target_year],
            ).fetchall()
        values = {int(r[0]): {"detections": int(r[1]), "total_frp": float(r[2] or 0.0)} for r in rows}
        current = values.get(target_year, {"detections": 0, "total_frp": 0.0})
        historical = [v["detections"] for y, v in values.items() if y < target_year]
        if not historical:
            raise ValueError("Not enough prior years in the local archive for this month")
        mean = sum(historical) / len(historical)
        stdev = math.sqrt(sum((x - mean) ** 2 for x in historical) / len(historical)) if len(historical) > 1 else 0.0
        z = (current["detections"] - mean) / stdev if stdev > 0 else (0.0 if current["detections"] == mean else (3.0 if current["detections"] > mean else -3.0))
        pct = ((current["detections"] - mean) / mean * 100.0) if mean > 0 else (100.0 if current["detections"] > 0 else 0.0)
        label = "exceptional" if z >= 2 else "elevated" if z >= 1 else "below-normal" if z <= -1 else "typical"
        return {
            "method": "local full-month same-month historical baseline",
            "source": source,
            "target_year": target_year,
            "target_month": target_month,
            "current_detections": current["detections"],
            "historical_mean": round(mean, 1),
            "historical_stdev": round(stdev, 2),
            "percent_change": round(pct, 1),
            "z_score": round(z, 2),
            "anomaly_label": label,
            "samples": [{"year": y, **v} for y, v in sorted(values.items())],
            "note": "Uses complete imported monthly observations for the selected AOI and one sensor family/source.",
        }


archive_store = ArchiveStore()
