#!/usr/bin/env python3
"""Sonda funcional: FPS, estabilidad de layout, capas GIBS vía proxy y clicks."""
from __future__ import annotations

import json
from playwright.sync_api import sync_playwright

PROBE = """async () => {
  const el = document.querySelector('.env-chip[data-env="pyro"]');
  let frames = 0;
  const boxes = [];
  const t0 = performance.now();
  await new Promise(res => {
    function loop() {
      frames++;
      if (frames % 10 === 0) boxes.push(JSON.stringify(el.getBoundingClientRect()));
      if (performance.now() - t0 < 2000) requestAnimationFrame(loop);
      else res();
    }
    requestAnimationFrame(loop);
  });
  return { fps: Math.round(frames / 2), cajas_distintas: new Set(boxes).size };
}"""


def main():
    reqs = {"proxy": 0, "osm": 0}
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.on("request", lambda r: reqs.__setitem__("proxy", reqs["proxy"] + 1) if "/api/gibs/tile/" in r.url else (reqs.__setitem__("osm", reqs["osm"] + 1) if "openstreetmap" in r.url else None))
        pg.goto("http://127.0.0.1:8000/", wait_until="domcontentloaded")
        pg.wait_for_timeout(9000)
        print("SONDA FPS/layout:", json.dumps(pg.evaluate(PROBE)))
        print("perf-soft:", pg.evaluate("() => document.body.classList.contains('perf-soft')"))

        pg.click('.env-chip[data-env="pyro"]', force=True)
        pg.wait_for_timeout(6000)
        print("chip pyro:", pg.evaluate('() => document.querySelector(\'.env-chip[data-env="pyro"]\').className'))
        pg.click('.env-chip[data-env="truecolor"]', force=True)
        pg.wait_for_timeout(6000)
        print("chip truecolor:", pg.evaluate('() => document.querySelector(\'.env-chip[data-env="truecolor"]\').className'))
        print("imagery layers:", pg.evaluate("() => viewer.imageryLayers.length"))
        print("peticiones:", reqs)
        pg.screenshot(path="/tmp/shot_capas2.png")

        pg.click('#viewMode .seg[data-mode="heat"]', force=True)
        pg.wait_for_timeout(1500)
        print("modo heat activo:", pg.evaluate('() => document.querySelector(\'#viewMode .seg[data-mode="heat"]\').classList.contains("active")'))
        pg.screenshot(path="/tmp/shot_heat.png")
        b.close()


if __name__ == "__main__":
    main()
