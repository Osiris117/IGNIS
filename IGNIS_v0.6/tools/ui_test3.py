#!/usr/bin/env python3
"""v0.9.4: COLOR REAL por defecto, idioma reactivo, timeline con debounce."""
from __future__ import annotations

import json
from playwright.sync_api import sync_playwright


def main():
    reqs = {"proxy": 0, "gibs_direct": 0}
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("request", lambda r: reqs.__setitem__("proxy", reqs["proxy"] + 1) if "/api/gibs/tile/" in r.url else (reqs.__setitem__("gibs_direct", reqs["gibs_direct"] + 1) if "gibs.earthdata" in r.url else None))
        pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
        pg.goto("http://127.0.0.1:8000/", wait_until="domcontentloaded")
        pg.wait_for_timeout(14000)  # arranque + COLOR REAL automático + tiles

        print("truecolor activo SIN click:", pg.evaluate('() => document.querySelector(\'.env-chip[data-env="truecolor"]\').classList.contains("active")'))
        print("capas de imagen (pila 3 días):", pg.evaluate("() => viewer.imageryLayers.length"))
        print("tooltips localizados (es):", pg.evaluate('() => document.querySelector(\'.env-chip[data-env="truecolor"]\').title'))
        pg.screenshot(path="/tmp/shot_v094_inicio.png")

        # idioma EN: los dinámicos deben repintarse
        pg.click('#langSwitch [data-lang="en"]')
        pg.wait_for_timeout(700)
        hdr = pg.evaluate("() => ({status: document.getElementById('systemStatus').textContent, sensors: document.getElementById('sensorName').textContent, feed: document.getElementById('feedMode').textContent, tip: document.querySelector('.env-chip[data-env=\"truecolor\"]').title})")
        print("tras EN:", json.dumps(hdr, ensure_ascii=False))
        pg.click('#langSwitch [data-lang="es"]')
        pg.wait_for_timeout(700)
        hdr2 = pg.evaluate("() => ({status: document.getElementById('systemStatus').textContent, sensors: document.getElementById('sensorName').textContent, tip: document.querySelector('.env-chip[data-env=\"truecolor\"]').title})")
        print("tras ES:", json.dumps(hdr2, ensure_ascii=False))

        # timeline: mover slider y comprobar debounce (sin reconstrucción inmediata)
        before = pg.evaluate("() => viewer.imageryLayers.length")
        reqs_before = reqs["proxy"]
        pg.evaluate("() => { const s=document.getElementById('frameSlider'); s.value=Math.max(0,Number(s.value)-1); s.dispatchEvent(new Event('input',{bubbles:true})); }")
        pg.wait_for_timeout(150)  # dentro de la ventana de debounce: NO debe haber recreado
        during = reqs["proxy"]
        pg.wait_for_timeout(2500)  # tras la pausa: refresca con fecha nueva
        print("peticiones proxy antes/durante(150ms)/después:", reqs_before, during, reqs["proxy"])
        print("capas antes/después:", before, pg.evaluate("() => viewer.imageryLayers.length"))
        pg.screenshot(path="/tmp/shot_v094_timeline.png")

        print("peticiones:", reqs, "· errores de página:", errs)
        b.close()


if __name__ == "__main__":
    main()
