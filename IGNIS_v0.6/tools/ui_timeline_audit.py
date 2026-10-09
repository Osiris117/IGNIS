#!/usr/bin/env python3
"""Regresión de capas y reproducción con respuestas de teselas controladas.

Uso: .venv/bin/python tools/ui_timeline_audit.py --url http://127.0.0.1:8000/
No consulta NASA/OSM: genera PNG válidos y simula espera, 404 y 502. Los clics
DOM ejercitan los manejadores; esta prueba no mide latencia de entrada física.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import struct
from urllib.parse import parse_qs, urlsplit
import zlib

from playwright.sync_api import sync_playwright


def fixture_png() -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    # PNG RGBA de 256 px, suficientemente opaco para probar continuidad visual.
    rows = b"".join(b"\0" + bytes((66, 102, 80, 255)) * 256 for _ in range(256))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def payload(start: str, days: int = 12) -> dict:
    first = date.fromisoformat(start)
    return {
        "mode": "harmonized-demo", "region": "mexico", "available_sources": ["MODIS_SP"], "events": [],
        "frames": [{"date": (first + timedelta(days=i)).isoformat(), "fires": [], "cells": [],
                    "summary": {"activity_mean": 0, "agreement_cells": 0}} for i in range(days)],
    }


def click_dom(page, selector: str) -> None:
    page.locator(selector).evaluate("element => element.click()")


def slider(page, index: int) -> None:
    page.locator("#frameSlider").evaluate("""(element, index) => {
        element.value = index;
        element.dispatchEvent(new Event('input', {bubbles:true}));
    }""", index)


def settle_layers(page) -> None:
    page.wait_for_function("() => typeof envPending !== 'undefined' && envPending.size === 0", timeout=20_000)


def state(page) -> dict:
    return page.evaluate("""() => {
      const id = (obj, map) => {
        if (!map.has(obj)) map.set(obj, ++window.__qaTimelineIdentity);
        return map.get(obj);
      };
      const imagery = Array.from({length:viewer.imageryLayers.length}, (_, i) => {
        const layer = viewer.imageryLayers.get(i), provider = layer.imageryProvider;
        return {id:id(layer, window.__qaTimelineLayers),
          provider:id(provider, window.__qaTimelineProviders), url:provider?.url || '',
          show:layer.show, alpha:layer.alpha};
      }).filter(x => x.url.includes('/api/gibs/'));
      return {
        date:currentEnvDate(), frameIndex, playing:!!playTimer,
        render:{loop:viewer.useDefaultRenderLoop,tilesLoaded:viewer.scene.globe.tilesLoaded,
          frame:viewer.scene.frameState?.frameNumber,requested:viewer.scene._renderRequested,
          width:viewer.canvas.width,height:viewer.canvas.height},
        chips:Object.fromEntries([...document.querySelectorAll('.env-chip')].map(x =>
          [x.dataset.env, {selected:x.getAttribute('aria-pressed') === 'true',
            active:x.classList.contains('active'), failed:x.classList.contains('failed'),
            degraded:x.classList.contains('degraded'), loading:x.classList.contains('loading'),
            title:x.title, state:x.dataset.state || ''}])),
        imagery,
        records:Object.fromEntries(Object.entries(envLayers).map(([key, rec]) =>
          [key, {date:rec.date || rec.requestedDate || null, ready:!!rec.ready,
            successes:rec.successes || 0, detailSuccesses:rec.detailSuccesses || 0,
            providers:(rec.layers || []).map(x => id(x.imageryProvider, window.__qaTimelineProviders))}])),
        events:window.__qaTimelineEvents.map(x => ({...x})),
        camera:[...['x','y','z'].map(k => viewer.camera.positionWC[k]),
                ...['x','y','z'].map(k => viewer.camera.directionWC[k])],
      };
    }""")


def selected(snapshot: dict) -> bool:
    return all(snapshot["chips"][key]["selected"] for key in ("truecolor", "aerosol"))


def providers(snapshot: dict) -> set[int]:
    return {x["provider"] for x in snapshot["imagery"] if x["show"] and x["alpha"] > 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--output", type=Path, default=Path("/tmp/ignis-timeline-audit"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result: dict = {"url": args.url, "fixtures": "synthetic PNG; controlled HTTP 200/404/502",
                    "input": "DOM clicks; no physical input latency claim", "checks": {}, "assertions": {}}
    errors: list[str] = []
    warnings: list[str] = []
    pending_routes = []
    network = {"hold": False, "status": 200, "counts": {"200": 0, "404": 0, "502": 0}, "held": 0}
    png = fixture_png()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="es-MX")
        context.route("https://**/*", lambda route: route.fulfill(content_type="image/png", body=png))

        def gibs(route):
            if network["hold"]:
                pending_routes.append(route)
                network["held"] += 1
                return
            status = network["status"]
            network["counts"][str(status)] += 1
            if status == 200:
                route.fulfill(content_type="image/png", body=png)
            else:
                route.fulfill(status=status, content_type="application/json",
                              body=json.dumps({"detail": "controlled no coverage" if status == 404 else "controlled upstream failure"}))

        context.route("**/api/gibs/**", gibs)
        context.route("**/api/harmonize/demo/date?**", lambda route: route.fulfill(json=payload(
            parse_qs(urlsplit(route.request.url).query)["start_date"][0], 3)))
        context.route("**/api/analytics/calendar/demo?**", lambda route: route.fulfill(json={
            "mode": "demo-calendar", "region_label": "Mexico", "start_year": 2024, "end_year": 2024,
            "rows": [{"year": 2024, "months": [{"month": 6, "available": True, "score": 30,
                                                 "detections": 10, "level": "moderate"}]}],
        }))
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: warnings.append(message.text) if message.type == "warning" else None)
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_function("() => typeof frames !== 'undefined' && frames.length > 1", timeout=30_000)
            # Esperar el alta diferida de COLOR REAL antes de fijar la secuencia.
            page.wait_for_function("() => envLayers.truecolor", timeout=15_000)
            page.wait_for_timeout(3_000)
            page.evaluate("""data => {
              if (playTimer) togglePlay();
              Object.keys(envLayers).forEach(removeEnvLayer);
              applyHarmonized(data); setViewMode('hotspots');
              viewer.camera.cancelFlight();
              viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(-102, 23, 4300000)});
              window.__qaTimelineIdentity=0;
              window.__qaTimelineProviders=new WeakMap();
              window.__qaTimelineLayers=new WeakMap();
              window.__qaTimelineEvents=[];
              for (const [event, action] of [[viewer.imageryLayers.layerAdded, 'add'],
                                           [viewer.imageryLayers.layerRemoved, 'remove']]) {
                event.addEventListener(layer => {
                  const url=layer.imageryProvider?.url || '';
                  if (url.includes('/api/gibs/')) window.__qaTimelineEvents.push({action, url});
                });
              }
            }""", payload("2024-07-01"))
            # Primera carga sin una imagen anterior: pulsar reproducir no
            # convierte una capa sin cobertura confirmada en una capa lista.
            network["hold"] = True
            initial_held_before = network["held"]
            click_dom(page, '.env-chip[data-env="truecolor"]')
            for _ in range(20):
                page.wait_for_timeout(100)
                if network["held"] > initial_held_before:
                    break
            initial_pending = page.evaluate("""() => {
              const rec=envPending.get('truecolor'), date=currentEnvDate();
              window.__qaInitialPending=rec;
              const before={pending:!!rec,ready:!!rec?.ready,successes:rec?.successes || 0};
              document.getElementById('btnPlay').click();
              document.getElementById('btnPlay').click();
              return {before,after:{samePending:!!rec && envPending.get('truecolor')===rec,
                ready:!!rec?.ready,successes:rec?.successes || 0,
                sameDate:currentEnvDate()===date,
                selected:document.querySelector('.env-chip[data-env="truecolor"]').getAttribute('aria-pressed')==='true'}};
            }""")
            page.wait_for_timeout(800)
            initial_pending["samePendingAfterDebounce"] = page.evaluate(
                "() => !!window.__qaInitialPending && envPending.get('truecolor') === window.__qaInitialPending")
            result["checks"]["first_load_play_pause_without_tiles"] = initial_pending
            result["assertions"]["first_load_has_retained_requests"] = (
                network["held"] > initial_held_before and initial_pending["before"]["pending"]
                and not initial_pending["before"]["ready"] and initial_pending["before"]["successes"] == 0)
            result["assertions"]["first_load_play_keeps_pending_validation"] = (
                initial_pending["after"]["samePending"] and not initial_pending["after"]["ready"]
                and initial_pending["after"]["successes"] == 0 and initial_pending["after"]["sameDate"]
                and initial_pending["after"]["selected"] and initial_pending["samePendingAfterDebounce"])
            network["hold"] = False
            for route in pending_routes:
                route.fulfill(content_type="image/png", body=png)
                network["counts"]["200"] += 1
            pending_routes.clear()
            settle_layers(page)
            first_loaded = state(page)
            result["checks"]["first_load_after_release"] = first_loaded
            first_record = first_loaded["records"].get("truecolor", {})
            result["assertions"]["first_load_finishes_with_data"] = (
                first_record.get("ready", False) and first_record.get("successes", 0) > 0
                and not first_loaded["chips"]["truecolor"]["failed"])
            click_dom(page, '.env-chip[data-env="aerosol"]')
            settle_layers(page)
            before = state(page)
            result["checks"]["initial"] = before
            result["assertions"]["successful_tiles_observed"] = network["counts"]["200"] > 0 and len(providers(before)) == 2

            # Reproducir/pausar/reproducir antes del primer tick no cambia fecha.
            # Una sola tarea del navegador impide que la latencia variable de
            # SwiftShader deje entrar un tick y cambie accidentalmente la fecha.
            page.evaluate("() => { for(let i=0;i<4;i++) document.getElementById('btnPlay').click(); }")
            page.wait_for_timeout(800)
            same = state(page)
            result["checks"]["same_date_play_pause_resume"] = same
            result["assertions"]["same_date_reuses_providers"] = providers(before) == providers(same)
            result["assertions"]["same_date_creates_no_layers"] = before["events"] == same["events"]
            result["assertions"]["play_keeps_camera"] = max(abs(a-b) for a, b in zip(before["camera"], same["camera"])) < 0.001

            click_dom(page, "#btnPlay")
            page.wait_for_timeout(1_950)
            playing = state(page)
            result["checks"]["playing_across_dates"] = playing
            result["assertions"]["play_advances_frames"] = playing["date"] != same["date"]
            result["assertions"]["play_retains_imagery"] = providers(playing) == providers(same)
            click_dom(page, "#btnPlay")
            page.wait_for_timeout(1_200)
            settle_layers(page)
            paused = state(page)
            result["checks"]["paused_after_ticks"] = paused

            # Retener HTTP demuestra que las imágenes anteriores siguen
            # dibujables mientras las de la fecha nueva aún no están listas.
            network["hold"] = True
            prior = state(page)
            slider(page, 8)
            page.wait_for_timeout(900)
            delayed = state(page)
            result["checks"]["replacement_delayed"] = delayed
            result["assertions"]["delayed_tiles_requested"] = network["held"] > 0
            result["assertions"]["replacement_keeps_old_images"] = bool(providers(prior)) and providers(prior).issubset(providers(delayed))
            result["assertions"]["replacement_keeps_selection"] = selected(delayed)
            network["hold"] = False
            for route in pending_routes:
                route.fulfill(content_type="image/png", body=png)
                network["counts"]["200"] += 1
            pending_routes.clear()
            settle_layers(page)
            replacement = state(page)
            result["checks"]["replacement_ready"] = replacement
            result["assertions"]["replacement_completes"] = selected(replacement) and providers(replacement) != providers(prior)
            # El servidor compone COLOR REAL; dos opciones producen dos capas
            # visibles. Una caché oculta puede permanecer sin duplicar pintura.
            result["assertions"]["no_accumulated_visible_images"] = len(providers(replacement)) == 2
            page.screenshot(path=str(args.output / "timeline_capas.png"))

            network["status"] = 404
            slider(page, 6)
            page.wait_for_timeout(600)
            settle_layers(page)
            missing = state(page)
            result["checks"]["missing_coverage_404"] = missing
            result["assertions"]["coverage_404_keeps_selection"] = selected(missing) and network["counts"]["404"] > 0

            # Obtener otra fecha utilizable antes de simular fallo de proveedor.
            network["status"] = 200
            slider(page, 5)
            page.wait_for_timeout(600)
            settle_layers(page)
            usable = state(page)
            network["status"] = 502
            slider(page, 4)
            page.wait_for_timeout(600)
            settle_layers(page)
            failed = state(page)
            result["checks"]["upstream_502"] = failed
            result["assertions"]["upstream_502_keeps_selection"] = selected(failed) and network["counts"]["502"] > 0
            result["assertions"]["upstream_502_shows_feedback"] = any(
                failed["chips"][key]["failed"] or failed["chips"][key]["degraded"]
                for key in ("truecolor", "aerosol"))
            result["assertions"]["upstream_502_keeps_old_images"] = bool(providers(usable)) and providers(usable).issubset(providers(failed))

            # Ejercitar la celda visible del calendario y su carga asíncrona.
            network["status"] = 200
            calendar_before = state(page)
            click_dom(page, "#btnCalendar")
            page.wait_for_selector('.cal-cell[data-year="2024"][data-month="6"]')
            click_dom(page, '.cal-cell[data-year="2024"][data-month="6"]')
            page.wait_for_function("() => frames[0]?.date === '2024-06-10'", timeout=10_000)
            page.wait_for_timeout(2_000)
            settle_layers(page)
            calendar = state(page)
            result["checks"]["calendar_new_period"] = calendar
            result["assertions"]["calendar_keeps_selection"] = selected(calendar)
            result["assertions"]["calendar_loads_date"] = page.locator("#historyDate").input_value() == "2024-06-10"
            result["assertions"]["calendar_same_region_keeps_camera"] = max(
                abs(a-b) for a, b in zip(calendar_before["camera"], calendar["camera"])) < 0.001
            page.screenshot(path=str(args.output / "calendario_capas.png"))
        except Exception as error:
            result["exception"] = f"{type(error).__name__}: {error}"
            result["assertions"]["audit_completed"] = False
        finally:
            result["errors"] = errors
            result["warnings"] = warnings
            result["network"] = {key: value for key, value in network.items() if key != "hold"}
            result["assertions"]["no_page_errors"] = not errors
            result["passed"] = bool(result["assertions"]) and all(result["assertions"].values())
            browser.close()

    (args.output / "timeline_resultados.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "assertions": result["assertions"],
                      "network": result["network"], "errors": errors,
                      "exception": result.get("exception"), "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
