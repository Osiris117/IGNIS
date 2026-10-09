#!/usr/bin/env python3
"""Auditoría reproducible de IGNIS en Chromium headless con SwiftShader.

Uso: .venv/bin/python tools/ui_audit.py --url http://127.0.0.1:8017/
Genera capturas y resultados.json en el directorio indicado con --output.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright


def snapshot(page, output: Path, name: str) -> str:
    path = output / f"{name}.png"
    # El modo bajo demanda puede estar en reposo. Solicitar un frame para la
    # captura no reactiva un pulso permanente en la aplicación.
    page.evaluate("viewer.scene.requestRender()")
    page.screenshot(path=str(path), timeout=45_000)
    return str(path)


def state(page) -> dict:
    return page.evaluate("""() => ({
      renderer: document.getElementById('rendererStatus')?.textContent?.trim(),
      perfSoft: document.body.classList.contains('perf-soft'),
      imageryLayers: viewer.imageryLayers.length,
      activeLayers: [...document.querySelectorAll('.env-chip.active')].map(x => x.dataset.env),
      failedLayers: [...document.querySelectorAll('.env-chip.failed')].map(x => x.dataset.env),
      status: document.getElementById('systemStatus')?.textContent?.trim(),
      feed: document.getElementById('feedMode')?.textContent?.trim(),
      sensors: document.getElementById('sensorName')?.textContent?.trim(),
      truecolorTip: document.querySelector('.env-chip[data-env="truecolor"]')?.title,
      tooltips: (() => { const nodes = [...document.querySelectorAll('[data-tip]')];
        return {total: nodes.length, missing: nodes.filter(x => !x.title.trim()).map(x => x.id || x.dataset.tip)}; })(),
      lang: window.IGNIS_I18N?.lang,
      theme: document.documentElement.dataset.theme,
      hdr: viewer.scene.highDynamicRange,
      bloom: viewer.scene.postProcessStages.bloom?.enabled,
      cesiumErrorPanel: [...document.querySelectorAll('.cesium-widget-errorPanel')]
        .some(x => getComputedStyle(x).display !== 'none'),
      dossierVisible: (() => { const x = document.getElementById('detailCard');
        return !!x && getComputedStyle(x).display !== 'none'; })(),
      globeTilesLoaded: viewer.scene.globe.tilesLoaded,
      cameraHeightMeters: Math.round(viewer.camera.positionCartographic.height),
    })""")


CLICK_RESULTS: list[dict] = []


def click_control(page, selector: str) -> None:
    """Prueba entrada física; registra los timeouts del compositor por software.

    El fallback DOM permite terminar las comprobaciones funcionales y queda
    explícito en resultados.json, sin confundirlo con un clic físico exitoso.
    """
    page.locator(selector).evaluate("""element => {
      element.dataset.qaClickCount = '0';
      element.addEventListener('click', () => {
        element.dataset.qaClickCount = String(Number(element.dataset.qaClickCount) + 1);
      }, {once: true});
    }""")
    started = time.perf_counter()
    result = {"selector": selector, "domFallback": False}
    try:
        page.locator(selector).click(force=True, timeout=5_000)
    except PlaywrightTimeoutError:
        result["physicalTimeout"] = True
        already_clicked = page.locator(selector).evaluate("element => Number(element.dataset.qaClickCount) > 0")
        if not already_clicked:
            result["domFallback"] = True
            page.locator(selector).evaluate("element => element.click()")
    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    CLICK_RESULTS.append(result)


def set_layer(page, key: str, enabled: bool) -> None:
    locator = page.locator(f'.env-chip[data-env="{key}"]')
    active = locator.get_attribute("aria-pressed") == "true"
    if active != enabled:
        click_control(page, f'.env-chip[data-env="{key}"]')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--output", type=Path, default=Path("/tmp/ignis-ui-audit"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    requests = {"osm": 0, "proxy_gibs": 0, "gibs_direct": 0}
    proxy_status: dict[str, int] = {}
    proxy_levels: dict[str, dict[str, int]] = {}
    proxy_level_status: dict[str, dict[str, int]] = {}
    errors: list[str] = []
    results: dict = {"url": args.url, "screenshots": {}, "checks": {}}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=[
            "--use-gl=swiftshader", "--enable-unsafe-swiftshader",
        ])
        context = browser.new_context(
            viewport={"width": 1600, "height": 900}, locale="es-MX",
            device_scale_factor=1,
        )
        page = context.new_page()

        def on_request(request):
            url = request.url
            if "tile.openstreetmap.org" in url:
                requests["osm"] += 1
            elif "/api/gibs/" in url:
                requests["proxy_gibs"] += 1
                match = re.search(r"/api/gibs/(?:tile/([^/]+)/|composite/)[^/]+/(\d+)/", url)
                if match:
                    layer, level = match.groups()
                    layer = layer or "truecolor-composite"
                    levels = proxy_levels.setdefault(layer, {})
                    levels[level] = levels.get(level, 0) + 1
            elif "gibs.earthdata.nasa.gov" in url:
                requests["gibs_direct"] += 1

        def on_response(response):
            if "/api/gibs/" in response.url:
                key = str(response.status)
                proxy_status[key] = proxy_status.get(key, 0) + 1
                match = re.search(r"/api/gibs/(?:tile/([^/]+)/|composite/)[^/]+/(\d+)/", response.url)
                if match:
                    layer, level = match.groups()
                    layer = layer or "truecolor-composite"
                    level_key = f"{layer}/z{level}"
                    statuses = proxy_level_status.setdefault(level_key, {})
                    statuses[key] = statuses.get(key, 0) + 1

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("console", lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(f"pageerror: {err}"))
        page.goto(args.url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_function("() => typeof viewer !== 'undefined' && !!document.getElementById('rendererStatus')", timeout=30_000)
        page.wait_for_function("() => document.querySelector('.env-chip[data-env=\"truecolor\"]')?.classList.contains('active')", timeout=30_000)
        page.wait_for_timeout(8_000)
        results["checks"]["inicio"] = state(page)
        results["checks"]["inicio"]["proxyRequestsByLevel"] = json.loads(json.dumps(proxy_levels))
        results["checks"]["inicio"]["proxyResponsesByStatus"] = proxy_status.copy()
        results["checks"]["inicio"]["proxyResponsesByLevel"] = json.loads(json.dumps(proxy_level_status))
        results["screenshots"]["inicio"] = snapshot(page, args.output, "inicio")
        page.wait_for_timeout(20_000)
        results["checks"]["inicio_30s"] = state(page)
        results["checks"]["inicio_30s"]["proxyRequestsByLevel"] = json.loads(json.dumps(proxy_levels))
        results["checks"]["inicio_30s"]["proxyResponsesByStatus"] = proxy_status.copy()
        results["checks"]["inicio_30s"]["proxyResponsesByLevel"] = json.loads(json.dumps(proxy_level_status))
        results["screenshots"]["inicio_30s"] = snapshot(page, args.output, "inicio_30s")

        # Aislar los productos ambientales para atribuir defectos visuales.
        for key in ("aerosol", "ndvi", "pyro", "truecolor"):
            set_layer(page, key, False)
        page.wait_for_timeout(1_500)
        results["screenshots"]["base"] = snapshot(page, args.output, "base")
        for key in ("aerosol", "pyro", "ndvi", "truecolor"):
            set_layer(page, key, True)
            page.wait_for_timeout(5_000)
            results["checks"][key] = state(page)
            results["screenshots"][key] = snapshot(page, args.output, key)
            set_layer(page, key, False)

        set_layer(page, "truecolor", True)
        set_layer(page, "aerosol", True)
        set_layer(page, "pyro", True)
        page.wait_for_timeout(4_000)
        results["screenshots"]["capas_juntas"] = snapshot(page, args.output, "capas_juntas")

        # Clic real, sin espera de accionabilidad que SwiftShader puede hambrear.
        page.evaluate("document.querySelector('#viewMode').scrollIntoView({block: 'nearest'})")
        page.wait_for_timeout(150)
        start = time.perf_counter()
        click_control(page, '#viewMode .seg[data-mode="heat"]')
        results["checks"]["modo_calor_click_retorno_ms"] = round((time.perf_counter() - start) * 1000)
        page.wait_for_function("() => document.querySelector('#viewMode .seg[data-mode=\"heat\"]')?.classList.contains('active')", timeout=10_000)
        results["checks"]["modo_calor_ms"] = round((time.perf_counter() - start) * 1000)
        results["checks"]["modo_calor_handler_ms"] = page.evaluate("""() => {
          setViewMode('hotspots');
          const t0 = performance.now();
          document.querySelector('#viewMode .seg[data-mode="heat"]').click();
          return {duration: Math.round((performance.now() - t0) * 10) / 10,
                  activeImmediately: document.querySelector('#viewMode .seg[data-mode="heat"]').classList.contains('active')};
        }""")

        results["checks"]["idioma_antes"] = state(page)
        click_control(page, '#langSwitch [data-lang="en"]')
        page.wait_for_timeout(500)
        results["checks"]["idioma_en"] = state(page)
        click_control(page, '#langSwitch [data-lang="es"]')
        page.wait_for_timeout(500)
        results["checks"]["idioma_es"] = state(page)

        click_control(page, '#themeToggle')
        page.wait_for_timeout(800)
        results["checks"]["tema_claro"] = state(page)
        results["screenshots"]["tema_claro"] = snapshot(page, args.output, "tema_claro")
        click_control(page, '#themeToggle')
        page.wait_for_timeout(500)
        results["checks"]["tema_oscuro"] = state(page)

        # Observar identidad de provider: durante 150 ms debe conservarse;
        # tras el debounce debe cambiar una vez a la fecha del nuevo frame.
        results["checks"]["timeline"] = page.evaluate("""() => {
          window.__qaLayer = envLayers.truecolor.layers[0];
          const slider = document.getElementById('frameSlider');
          const from = Number(slider.value);
          const to = from > 0 ? from - 1 : from + 1;
          slider.value = to;
          slider.dispatchEvent(new Event('input', {bubbles: true}));
          return {from, to, max: Number(slider.max), dateBefore: envLayerDate,
                  sameImmediately: envLayers.truecolor.layers[0] === window.__qaLayer};
        }""")
        page.wait_for_timeout(150)
        results["checks"]["timeline"]["sameAt150ms"] = page.evaluate(
            "() => envLayers.truecolor.layers[0] === window.__qaLayer"
        )
        page.wait_for_function("() => envPending.size === 0", timeout=20_000)
        results["checks"]["timeline"].update(page.evaluate("""() => ({
          sameAfterPause: envLayers.truecolor.layers[0] === window.__qaLayer,
          dateAfter: envLayerDate,
          layerCount: viewer.imageryLayers.length,
        })"""))
        results["screenshots"]["timeline"] = snapshot(page, args.output, "timeline")

        # El demo abre un seguimiento solo al pedirlo; revisar su dossier y la
        # microcopia del analista en ambos idiomas con contenido ya renderizado.
        click_control(page, '#btnEvolutionDemo')
        page.wait_for_function("() => getComputedStyle(document.getElementById('detailCard')).display !== 'none'", timeout=20_000)
        page.wait_for_timeout(1_000)

        def dossier_texts():
            return page.evaluate("""() => ({
              visible: getComputedStyle(document.getElementById('detailCard')).display !== 'none',
              state: document.getElementById('detailSeverity').textContent.trim(),
              tracking: document.getElementById('trackingState').textContent.trim(),
              analystHint: document.getElementById('analystHint').textContent.trim(),
              language: window.IGNIS_I18N.lang,
            })""")

        results["checks"]["dossier_es"] = dossier_texts()
        results["screenshots"]["dossier_es"] = snapshot(page, args.output, "dossier_es")
        click_control(page, '#langSwitch [data-lang="en"]')
        page.wait_for_timeout(500)
        results["checks"]["dossier_en"] = dossier_texts()
        results["screenshots"]["dossier_en"] = snapshot(page, args.output, "dossier_en")
        click_control(page, '#langSwitch [data-lang="es"]')
        page.wait_for_timeout(500)
        results["checks"]["dossier_es_retorno"] = dossier_texts()

        results["requests"] = requests.copy()
        results["proxy_status"] = proxy_status.copy()
        results["proxy_levels"] = proxy_levels.copy()
        results["proxy_level_status"] = proxy_level_status.copy()
        results["errors_before_offline"] = [e for e in errors if "favicon" not in e.lower()]

        # Desconectar internet conservando el servidor local y sus recursos.
        context.route("https://**/*", lambda route: route.abort())
        page.evaluate("window.dispatchEvent(new Event('offline'))")
        page.wait_for_timeout(500)
        results["checks"]["offline"] = state(page)
        results["screenshots"]["offline"] = snapshot(page, args.output, "offline")
        results["checks"]["offline"]["localBasemap"] = page.evaluate("() => ignisBaseFallbackUsed")
        results["physical_clicks"] = CLICK_RESULTS
        browser.close()

    results["assertions"] = {
        "swiftshader_detectado": results["checks"]["inicio"]["perfSoft"],
        "color_real_inicio": "truecolor" in results["checks"]["inicio"]["activeLayers"],
        "inicio_sin_dossier": not results["checks"]["inicio"]["dossierVisible"],
        "sin_modal_cesium": not results["checks"]["inicio"]["cesiumErrorPanel"],
        "proxy_usado": requests["proxy_gibs"] > 0,
        "sin_gibs_directo": requests["gibs_direct"] == 0,
        "sin_errores_js": len(results["errors_before_offline"]) == 0,
        "idioma_reactivo": results["checks"]["idioma_en"]["truecolorTip"] != results["checks"]["idioma_es"]["truecolorTip"],
        "tooltips_completos": not results["checks"]["idioma_en"]["tooltips"]["missing"] and not results["checks"]["idioma_es"]["tooltips"]["missing"],
        "tema_sw_sin_hdr": not results["checks"]["tema_claro"]["hdr"] and not results["checks"]["tema_oscuro"]["hdr"],
        "timeline_debounce": results["checks"]["timeline"]["sameAt150ms"] and not results["checks"]["timeline"]["sameAfterPause"],
        "dossier_bilingue": (
            results["checks"]["dossier_es"]["visible"]
            and results["checks"]["dossier_es"]["state"] != results["checks"]["dossier_en"]["state"]
            and results["checks"]["dossier_es"]["analystHint"] != results["checks"]["dossier_en"]["analystHint"]
            and results["checks"]["dossier_es"]["state"] == results["checks"]["dossier_es_retorno"]["state"]
        ),
        "offline_sin_capas": len(results["checks"]["offline"]["activeLayers"]) == 0,
        "offline_mapa_local": results["checks"]["offline"]["localBasemap"],
    }
    path = args.output / "resultados.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"assertions": results["assertions"], "requests": requests,
                      "proxy_status": proxy_status, "proxy_levels": proxy_levels,
                      "errors": results["errors_before_offline"],
                      "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0 if all(results["assertions"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
