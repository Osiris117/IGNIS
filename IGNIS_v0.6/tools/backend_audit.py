#!/usr/bin/env python3
"""Pruebas aisladas del backend IGNIS; ejecutar con .venv/bin/python tools/backend_audit.py.

No consulta NASA ni escribe el registro de evolución: reemplaza el cliente GIBS
del lifespan por respuestas HTTP simuladas y usa persist=False para las pistas.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.app as ignis  # noqa: E402
from backend.context_engine import _mean_angle  # noqa: E402
from backend.evolution_engine import track_evolution  # noqa: E402


TRUECOLOR = "MODIS_Terra_CorrectedReflectance_TrueColor"
AOD = "MODIS_Terra_Aerosol"
DAY = "2024-07-01"
BASE = "/api/gibs/tile"


def _in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray casting for the independent Natural Earth land fixture."""
    inside = False
    for index in range(len(ring)):
        ax, ay = ring[index - 1]
        bx, by = ring[index]
        if (ay > lat) != (by > lat) and lon < (bx - ax) * (lat - ay) / (by - ay) + ax:
            inside = not inside
    return inside


def _land_polygons() -> list[tuple[tuple[float, float, float, float], list[list[list[float]]]]]:
    # Natural Earth, public domain, 1:110m land polygons. Kept local so the
    # regression runs offline: https://github.com/nvkelso/natural-earth-vector/
    # blob/master/geojson/ne_110m_land.geojson
    source = Path(__file__).resolve().parent / "fixtures" / "ne_110m_land.geojson"
    features = json.loads(source.read_text(encoding="utf-8"))["features"]
    polygons = []
    for feature in features:
        rings = feature["geometry"]["coordinates"]
        longitudes = [lon for ring in rings for lon, _ in ring]
        latitudes = [lat for ring in rings for _, lat in ring]
        polygons.append(((min(longitudes), min(latitudes), max(longitudes), max(latitudes)), rings))
    return polygons


def _on_land(lat: float, lon: float, polygons) -> bool:
    for (west, south, east, north), rings in polygons:
        if west <= lon <= east and south <= lat <= north:
            if _in_ring(lon, lat, rings[0]) and not any(_in_ring(lon, lat, hole) for hole in rings[1:]):
                return True
    return False


def sample_jpeg() -> bytes:
    """JPEG con hueco de órbita y terreno oscuro separado de ese hueco."""
    image = Image.new("RGB", (256, 256), (110, 145, 165))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 80, 100), fill=(0, 0, 0))
    draw.rectangle((180, 180, 230, 230), fill=(20, 25, 30))
    output = io.BytesIO()
    image.save(output, "JPEG", quality=95, subsampling=0)
    return output.getvalue()


def sample_png() -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (256, 256), (12, 34, 56, 200)).save(output, "PNG")
    return output.getvalue()


def layered_jpeg(color: tuple[int, int, int], gap: tuple[int, int, int, int] | None = None) -> bytes:
    image = Image.new("RGB", (256, 256), color)
    if gap:
        ImageDraw.Draw(image).rectangle(gap, fill=(0, 0, 0))
    output = io.BytesIO()
    image.save(output, "JPEG", quality=100, subsampling=0)
    return output.getvalue()


class FakeGibsClient:
    def __init__(self, answer):
        self.answer = answer
        self.urls: list[str] = []

    async def get(self, url: str) -> httpx.Response:
        self.urls.append(url)
        result = self.answer(url)
        if isinstance(result, Exception):
            raise result
        status, body = result
        return httpx.Response(status, content=body, request=httpx.Request("GET", url))


class BackendAudit(unittest.TestCase):
    def setUp(self) -> None:
        ignis._GIBS_TILE_CACHE.clear()
        ignis._GIBS_CACHE_BYTES = 0
        self.session = TestClient(ignis.app)
        self.client = self.session.__enter__()
        self.real_gibs_client = ignis.app.state.gibs_client

    def tearDown(self) -> None:
        ignis.app.state.gibs_client = self.real_gibs_client
        self.session.__exit__(None, None, None)

    def fake(self, answer) -> FakeGibsClient:
        client = FakeGibsClient(answer)
        ignis.app.state.gibs_client = client
        return client

    def test_truecolor_png_alpha_and_cache_date(self) -> None:
        fake = self.fake(lambda _url: (200, sample_jpeg()))
        path = f"{BASE}/{TRUECOLOR}/{DAY}/5/14/7.png"
        first = self.client.get(path)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["content-type"], "image/png")
        self.assertEqual(first.headers["x-gibs-date"], DAY)
        self.assertEqual(first.headers["x-gibs-cache"], "miss")
        self.assertEqual(len(fake.urls), 1)
        self.assertTrue(fake.urls[0].endswith(f"/{DAY}/GoogleMapsCompatible_Level9/5/14/7.jpg"))
        image = Image.open(io.BytesIO(first.content))
        self.assertEqual((image.format, image.mode, image.size), ("PNG", "RGBA", (256, 256)))
        alpha = image.getchannel("A")
        self.assertEqual(alpha.getpixel((50, 50)), 0)
        self.assertEqual(alpha.getpixel((200, 200)), 255)
        self.assertEqual(alpha.getpixel((130, 130)), 255)

        second = self.client.get(path)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.headers["x-gibs-cache"], "hit")
        self.assertEqual(second.headers["x-gibs-date"], DAY)
        self.assertEqual(second.content, first.content)
        self.assertEqual(len(fake.urls), 1)

    def test_low_lod_png_is_transparent_without_upstream(self) -> None:
        fake = self.fake(lambda _url: AssertionError("unexpected GIBS request"))
        for z, y, x in ((0, 0, 0), (4, 7, 3)):
            with self.subTest(level=z):
                response = self.client.get(f"{BASE}/{TRUECOLOR}/{DAY}/{z}/{y}/{x}.png")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["content-type"], "image/png")
                self.assertEqual(response.headers["x-gibs-lod"], "omitted-below-5")
                image = Image.open(io.BytesIO(response.content))
                self.assertEqual((image.format, image.mode, image.size), ("PNG", "RGBA", (256, 256)))
                self.assertEqual(image.getchannel("A").getextrema(), (0, 0))
        self.assertEqual(fake.urls, [])

    def test_validation_happens_before_low_lod_bypass(self) -> None:
        fake = self.fake(lambda _url: AssertionError("unexpected GIBS request"))
        invalid = (
            (f"{BASE}/{TRUECOLOR}/not-a-date/0/0/0.png", 400),
            (f"{BASE}/{TRUECOLOR}/1999-12-31/0/0/0.png", 400),
            (f"{BASE}/{TRUECOLOR}/{date.today().year + 1}-01-01/0/0/0.png", 400),
            (f"{BASE}/{TRUECOLOR}/{DAY}/0/1/0.png", 400),
            (f"{BASE}/{TRUECOLOR}/{DAY}/10/0/0.png", 400),
            (f"{BASE}/unknown/{DAY}/0/0/0.png", 404),
            (f"{BASE}/{AOD}/{DAY}/0/0/0.jpg", 404),
        )
        for path, expected in invalid:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, expected)
        self.assertEqual(fake.urls, [])

    def test_date_fallback_and_png_cache(self) -> None:
        png = sample_png()
        fake = self.fake(lambda url: (200, png) if "/2024-06-29/" in url else (404, b""))
        path = f"{BASE}/{AOD}/{DAY}/5/14/7.png"
        first = self.client.get(path)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["content-type"], "image/png")
        self.assertEqual(first.headers["x-gibs-date"], "2024-06-29")
        self.assertEqual(first.headers["x-gibs-cache"], "miss")
        self.assertEqual(len(fake.urls), 3)
        self.assertEqual(Image.open(io.BytesIO(first.content)).format, "PNG")
        second = self.client.get(path)
        self.assertEqual(second.headers["x-gibs-date"], "2024-06-29")
        self.assertEqual(second.headers["x-gibs-cache"], "hit")
        self.assertEqual(len(fake.urls), 3)

    def test_no_coverage_is_404_after_five_dates(self) -> None:
        fake = self.fake(lambda _url: (404, b""))
        response = self.client.get(f"{BASE}/{AOD}/{DAY}/5/14/7.png")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(fake.urls), 5)

    def test_upstream_http_and_invalid_image_are_502(self) -> None:
        for answer in (lambda _url: (503, b""), lambda _url: (200, b"<html>not an image</html>")):
            with self.subTest(answer=answer):
                fake = self.fake(answer)
                with self.assertLogs(ignis.logger, level="WARNING"):
                    response = self.client.get(f"{BASE}/{AOD}/{DAY}/5/14/7.png")
                self.assertEqual(response.status_code, 502)
                self.assertEqual(len(fake.urls), 1)

    def test_connection_error_is_502_and_timeout_is_504(self) -> None:
        for error, expected in ((httpx.ConnectError("offline"), 502), (httpx.ReadTimeout("slow"), 504)):
            with self.subTest(error=type(error).__name__):
                fake = self.fake(lambda _url: error)
                with self.assertLogs(ignis.logger, level="WARNING"):
                    response = self.client.get(f"{BASE}/{AOD}/{DAY}/5/14/7.png")
                self.assertEqual(response.status_code, expected)
                self.assertEqual(len(fake.urls), 1)

    def test_failed_conversion_keeps_jpeg_media_type(self) -> None:
        fake = self.fake(lambda _url: (200, sample_jpeg()))
        with patch.object(ignis, "_transparentize_png", side_effect=ValueError("synthetic conversion failure")):
            with self.assertLogs(ignis.logger, level="ERROR"):
                response = self.client.get(f"{BASE}/{TRUECOLOR}/{DAY}/5/14/7.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertTrue(response.content.startswith(b"\xff\xd8\xff"))
        self.assertEqual(len(fake.urls), 1)

    def test_three_day_composite_layers_and_exact_date_cache(self) -> None:
        images = {
            "2024-06-29": layered_jpeg((210, 30, 30)),
            "2024-06-30": layered_jpeg((30, 210, 30), (64, 64, 192, 192)),
            "2024-07-01": layered_jpeg((30, 30, 210), (128, 0, 255, 255)),
            "2024-07-02": layered_jpeg((210, 210, 30)),
        }
        fake = self.fake(lambda url: (200, next(body for day, body in images.items() if f"/{day}/" in url)))
        path = f"/api/gibs/composite/{DAY}/5/14/7.png"
        first = self.client.get(path)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["content-type"], "image/png")
        self.assertEqual(first.headers["x-gibs-dates"], "2024-07-01,2024-06-30,2024-06-29")
        self.assertEqual(first.headers["x-gibs-partial"], "false")
        self.assertEqual(first.headers["x-gibs-cache"], "miss")
        self.assertEqual(len(fake.urls), 3)
        image = Image.open(io.BytesIO(first.content))
        self.assertEqual((image.format, image.mode, image.size), ("PNG", "RGBA", (256, 256)))
        blue, green, red = (image.getpixel(point) for point in ((20, 20), (220, 20), (150, 100)))
        self.assertGreater(blue[2], max(blue[0], blue[1]))
        self.assertGreater(green[1], max(green[0], green[2]))
        self.assertGreater(red[0], max(red[1], red[2]))

        second = self.client.get(path)
        self.assertEqual(second.headers["x-gibs-cache"], "hit")
        self.assertEqual(len(fake.urls), 3)
        adjacent = self.client.get("/api/gibs/composite/2024-07-02/5/14/7.png")
        self.assertEqual(adjacent.status_code, 200)
        self.assertEqual(len(fake.urls), 4)  # two exact dates reused, one new request

    def test_composite_partial_and_no_fallback_alias(self) -> None:
        oldest = layered_jpeg((210, 30, 30))
        fake = self.fake(lambda url: (200, oldest) if "/2024-06-29/" in url else (404, b""))
        tile = self.client.get(f"{BASE}/{TRUECOLOR}/{DAY}/5/14/7.png")
        self.assertEqual(tile.status_code, 200)
        self.assertEqual(tile.headers["x-gibs-date"], "2024-06-29")
        self.assertEqual(len(fake.urls), 3)
        composite = self.client.get(f"/api/gibs/composite/{DAY}/5/14/7.png")
        self.assertEqual(composite.status_code, 200)
        self.assertEqual(composite.headers["x-gibs-dates"], "2024-06-29")
        self.assertEqual(composite.headers["x-gibs-partial"], "true")
        self.assertLessEqual(int(composite.headers["cache-control"].split("=")[-1]), 120)
        self.assertEqual(len(fake.urls), 5)  # exact day-2 cache reused, not aliased as day 0

    def test_composite_low_lod_validation_and_provider_errors(self) -> None:
        fake = self.fake(lambda _url: AssertionError("unexpected GIBS request"))
        low = self.client.get(f"/api/gibs/composite/{DAY}/0/0/0.png")
        self.assertEqual(low.status_code, 200)
        self.assertEqual(low.headers["x-gibs-lod"], "omitted-below-5")
        self.assertEqual(Image.open(io.BytesIO(low.content)).getchannel("A").getextrema(), (0, 0))
        self.assertEqual(self.client.get(f"/api/gibs/composite/{DAY}/0/1/0.png").status_code, 400)
        self.assertEqual(fake.urls, [])

        for answer, expected in ((lambda _url: (404, b""), 404),
                                 (lambda _url: (503, b""), 502),
                                 (lambda _url: httpx.ReadTimeout("slow"), 504)):
            with self.subTest(status=expected):
                fake = self.fake(answer)
                if expected == 404:
                    response = self.client.get(f"/api/gibs/composite/{DAY}/5/14/7.png")
                else:
                    with self.assertLogs(ignis.logger, level="WARNING"):
                        response = self.client.get(f"/api/gibs/composite/{DAY}/5/14/7.png")
                self.assertEqual(response.status_code, expected)
                self.assertEqual(len(fake.urls), 3)

    def test_calendar_uses_server_date_boundary(self) -> None:
        class ServerDate(date):
            @classmethod
            def today(cls):
                return cls(2024, 7, 1)

        with patch.object(ignis, "date", ServerDate):
            self.assertEqual(self.client.get("/api/config").json()["current_date"], "2024-07-01")
            self.assertEqual(ignis._safe_date("2024-07-01"), "2024-07-01")
            with self.assertRaises(ignis.HTTPException) as error:
                ignis._safe_date("2024-07-02")
            self.assertEqual(error.exception.status_code, 400)

    def test_severity_and_circular_wind_regressions(self) -> None:
        self.assertEqual(_mean_angle([350.0, 10.0]), 0.0)
        frames = [
            {"date": "2024-07-01", "events": [{"lat": 20, "lon": -100, "severity": "critical", "detections": 2, "total_frp": 20}]},
            {"date": "2024-07-02", "events": [{"lat": 20, "lon": -100, "severity": "moderate", "detections": 2, "total_frp": 10}]},
        ]
        result = track_evolution(frames, session="BACKEND-AUDIT", persist=False)
        self.assertEqual(len(result["tracks"]), 1)
        self.assertEqual(result["tracks"][0]["severity"], "critical")

    def test_all_synthetic_demo_markers_and_cells_are_on_land(self) -> None:
        polygons = _land_polygons()
        self.assertFalse(_on_land(22.0, -95.0, polygons))  # Gulf of Mexico control
        self.assertFalse(_on_land(37.0, -124.0, polygons))  # Pacific control

        all_rows: list[tuple[str, dict]] = []
        fires_demo = self.client.get("/api/fires/demo")
        self.assertEqual(fires_demo.status_code, 200)
        self.assertTrue(fires_demo.json()["synthetic"])
        all_rows.extend(("fires/demo", item) for item in fires_demo.json()["fires"])

        harmonized = self.client.get("/api/harmonize/demo")
        self.assertEqual(harmonized.status_code, 200)
        self.assertTrue(harmonized.json()["synthetic"])
        for frame in harmonized.json()["frames"]:
            all_rows.extend(("harmonize/demo fire", item) for item in frame["fires"])
            all_rows.extend(("harmonize/demo cell", item) for item in frame["cells"])

        for region in ignis.REGIONS:
            for start in ("2024-01-01", "2024-07-01"):
                path = f"/api/harmonize/demo/date?region={region}&start_date={start}&days=5"
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertTrue(response.json()["synthetic"], path)
                for frame in response.json()["frames"]:
                    all_rows.extend((f"{region} {start} fire", item) for item in frame["fires"])
                    all_rows.extend((f"{region} {start} cell", item) for item in frame["cells"])

        for region in ("mexico", "amazon"):
            for frame in ignis._evolution_demo_frames(region, 10):
                all_rows.extend((f"evolution {region} fire", item) for item in frame["fires"])
                all_rows.extend((f"evolution {region} cell", item) for item in frame["cells"])

        self.assertGreater(len(all_rows), 3000)
        for source, item in all_rows:
            lat, lon = float(item["lat"]), float(item["lon"])
            with self.subTest(source=source, lat=lat, lon=lon):
                self.assertTrue(-90 <= lat <= 90 and -180 <= lon <= 180)
                self.assertTrue(_on_land(lat, lon, polygons))
                if "fire" in source:
                    self.assertTrue(item["synthetic"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
