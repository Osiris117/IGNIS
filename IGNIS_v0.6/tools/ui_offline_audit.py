#!/usr/bin/env python3
"""Arranque sin internet, conservando acceso al servidor local de IGNIS."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--output", type=Path, default=Path("/tmp/ignis-offline-audit"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=[
            "--use-gl=swiftshader", "--enable-unsafe-swiftshader",
        ])
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        # Simula internet caído. El backend y los recursos locales siguen
        # accesibles, como al ejecutar IGNIS en una máquina desconectada.
        context.route("https://**/*", lambda route: route.abort())
        context.route("**/api/gibs/**", lambda route: route.fulfill(
            status=502, content_type="application/json",
            body='{"detail":"NASA GIBS unavailable in offline test"}',
        ))
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_function("""() => typeof viewer !== 'undefined' &&
          viewer.imageryLayers.get(0)?.imageryProvider?.url?.includes('NaturalEarthII')
        """, timeout=30_000)
        page.wait_for_function("""() =>
          document.querySelector('.env-chip[data-env="truecolor"]').classList.contains('failed')
        """, timeout=30_000)
        page.wait_for_timeout(1_000)
        result = page.evaluate("""() => ({
          layers: viewer.imageryLayers.length,
          basemap: viewer.imageryLayers.get(0).imageryProvider.url,
          activeLayers: document.querySelectorAll('.env-chip.active').length,
          unavailableLayers: document.querySelectorAll('.env-chip.failed').length,
          frames: frames.length,
          renderLoop: viewer.useDefaultRenderLoop,
          modal: !!document.querySelector('.cesium-widget-errorPanel'),
        })""")
        result["pageErrors"] = errors
        result["passed"] = (
            result["layers"] == 1 and result["activeLayers"] == 0
            and result["unavailableLayers"] >= 1 and result["frames"] > 0
            and result["renderLoop"] and not result["modal"] and not errors
        )
        page.screenshot(path=str(args.output / "inicio_sin_internet.png"))
        browser.close()
    (args.output / "offline_resultados.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
