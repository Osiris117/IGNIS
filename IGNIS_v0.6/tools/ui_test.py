#!/usr/bin/env python3
"""Prueba de UI headless (Playwright) para IGNIS.

Abre la app, espera el arranque de Cesium, activa las capas ambientales,
revisa clases de los chips, cuenta peticiones a GIBS/OSM/proxy y captura
pantallas. Imprime un resumen accionable.
"""
from __future__ import annotations

import sys
import time
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

errors: list[str] = []
requests_log: dict[str, int] = {"osm": 0, "proxy_gibs": 0, "gibs_direct": 0, "api": 0}


def on_request(req):
    u = req.url
    if "tile.openstreetmap.org" in u:
        requests_log["osm"] += 1
    elif "/api/gibs/tile/" in u:
        requests_log["proxy_gibs"] += 1
    elif "gibs.earthdata.nasa.gov" in u:
        requests_log["gibs_direct"] += 1
    elif "/api/" in u:
        requests_log["api"] += 1


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type in ("error",) else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        page.on("request", on_request)

        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(7000)  # arranque de Cesium + intro de cámara

        renderer = page.evaluate("() => document.getElementById('rendererStatus')?.textContent")
        soft = page.evaluate("() => document.body.classList.contains('perf-soft')")
        print(f"RENDERER: {renderer} · perf-soft: {soft}")

        page.screenshot(path="/tmp/shot_inicio.png")

        # capa PIRO-CB (la que fallaba en la captura del usuario)
        page.click('.env-chip[data-env="pyro"]')
        page.wait_for_timeout(6000)
        cls = page.evaluate("() => document.querySelector('.env-chip[data-env=\"pyro\"]').className")
        print(f"CHIP pyro: {cls}")
        # capa AEROSOLES
        page.click('.env-chip[data-env="aerosol"]')
        page.wait_for_timeout(6000)
        cls2 = page.evaluate("() => document.querySelector('.env-chip[data-env=\"aerosol\"]').className")
        print(f"CHIP aerosol: {cls2}")
        page.screenshot(path="/tmp/shot_capas.png")

        # capas de imagen cargadas en Cesium
        layers = page.evaluate("() => viewer.imageryLayers.length")
        print(f"IMAGERY LAYERS en el globo: {layers}")

        # botón de la izquierda: cambiar modo de vista (prueba de respuesta UI)
        t0 = time.time()
        page.click('#viewMode .seg[data-mode="heat"]')
        page.wait_for_function("() => document.querySelector('#viewMode .seg[data-mode=\"heat\"]').classList.contains('active')")
        dt = (time.time() - t0) * 1000
        print(f"CLICK modo FUSION GRID aplicado en {dt:.0f} ms")
        page.click('#viewMode .seg[data-mode="evolution"]')
        page.wait_for_timeout(2500)
        page.screenshot(path="/tmp/shot_evolucion.png")

        # tema claro
        page.click('#themeToggle')
        page.wait_for_timeout(1200)
        theme = page.evaluate("() => document.documentElement.dataset.theme")
        print(f"TEMA tras toggle: {theme}")
        page.screenshot(path="/tmp/shot_light.png")

        print("PETICIONES:", requests_log)
        fatal = [e for e in errors if "favicon" not in e.lower()]
        print(f"ERRORES DE CONSOLA ({len(fatal)}):")
        for e in fatal[:12]:
            print("   ", e[:220])
        browser.close()

        ok = ("failed" not in cls) and ("failed" not in cls2) and requests_log["proxy_gibs"] > 0 and layers >= 3
        print("RESULTADO:", "OK" if ok else "REVISAR")
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
