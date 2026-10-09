#!/usr/bin/env python3
"""Regresión focalizada: detalle TrueColor fallido y ayuda con foco.

Usa PNG sintéticos. La segunda fecha devuelve PNG transparentes en z<5 y
aborta z>=5 sin código HTTP. Se simula una cola de teselas vacía durante la
notificación tileLoadProgress(0) para ejercitar expresamente el guard de check().
El timeout real de 18 s también debe conservar la imagen anterior.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import re
import struct
import zlib

from playwright.sync_api import sync_playwright


def png(alpha: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    data = b"".join(b"\0" + bytes((66, 102, 80, alpha)) * 256 for _ in range(256))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(data)) + chunk(b"IEND", b""))


def snapshot(page) -> dict:
    return page.evaluate("""() => {
      const old=window.__qaContinuityOld, pending=window.__qaContinuityPending;
      const chip=document.querySelector('.env-chip[data-env="truecolor"]');
      const layer=old?.layers[0];
      return {
        date:currentEnvDate(), visibleDate:envLayers.truecolor?.date || null,
        selected:chip.getAttribute('aria-pressed')==='true',
        active:chip.classList.contains('active'),failed:chip.classList.contains('failed'),
        sameOld:!!old && envLayers.truecolor===old,
        oldVisible:!!layer && viewer.imageryLayers.contains(layer) && layer.show && layer.alpha>0,
        pending:envPending.has('truecolor'),
        pendingSame:!!pending && envPending.get('truecolor')===pending,
        candidate:{ready:!!pending?.ready,successes:pending?.successes || 0,
          requestedDetail:!!pending?.requestedDetail,detailSuccesses:pending?.detailSuccesses || 0,
          httpFailures:pending?.failures.size || 0,missing:pending?.missing.size || 0},
        elapsedCandidateMs:pending ? Math.round(performance.now()-pending.used) : null,
        status:document.getElementById('envLayerStatus')?.textContent || '',
      };
    }""")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--output", type=Path, default=Path("/tmp/ignis-ui-correcciones-real"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    opaque, transparent = png(255), png(0)
    network = {"healthy": 0, "transparentLowLod": 0, "detailAbortedWithoutStatus": 0}
    errors = []
    result = {"url": args.url, "fixtures": "opaque PNG, transparent z<5 PNG, z>=5 network abort without HTTP status",
              "emptyQueueSimulatedForCheck": True, "checks": {}, "assertions": {}}
    target_date = "2024-06-30"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        context = browser.new_context(viewport={"width": 1280, "height": 800}, locale="es-MX")
        context.route("https://**/*", lambda route: route.fulfill(content_type="image/png", body=opaque))

        def gibs(route):
            match = re.search(r"/api/gibs/composite/([^/]+)/(\d+)/", route.request.url)
            if match and match.group(1) == target_date:
                if int(match.group(2)) >= 5:
                    network["detailAbortedWithoutStatus"] += 1
                    route.abort("failed")
                else:
                    network["transparentLowLod"] += 1
                    route.fulfill(content_type="image/png", body=transparent)
            else:
                network["healthy"] += 1
                route.fulfill(content_type="image/png", body=opaque)

        context.route("**/api/gibs/**", gibs)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_function("() => typeof frames !== 'undefined' && frames.length > 1", timeout=30_000)
            page.wait_for_function("() => envLayers.truecolor", timeout=15_000)
            page.wait_for_timeout(3_000)
            first = date(2024, 7, 1)
            payload = {"mode": "harmonized-demo", "region": "mexico", "events": [],
                       "frames": [{"date": (first + timedelta(days=i)).isoformat(), "fires": [], "cells": [],
                                   "summary": {"activity_mean": 0, "agreement_cells": 0}} for i in range(3)]}
            page.evaluate("""data => {
              [...envSelections].forEach(removeEnvLayer);
              applyHarmonized(data);setViewMode('hotspots');
              viewer.camera.cancelFlight();
              viewer.camera.setView({destination:Cesium.Cartesian3.fromDegrees(-102,23,2100000)});
              document.querySelector('.env-chip[data-env="truecolor"]').click();
            }""", payload)
            page.wait_for_function("""() => !envPending.has('truecolor') &&
              envLayers.truecolor?.ready && envLayers.truecolor.detailSuccesses>0
            """, timeout=25_000)
            page.evaluate("() => { window.__qaContinuityOld=envLayers.truecolor; }")
            result["checks"]["loaded_old_image"] = snapshot(page)
            result["assertions"]["old_image_loaded"] = result["checks"]["loaded_old_image"]["oldVisible"]

            page.locator("#frameSlider").evaluate("""slider => {
              slider.value=1;slider.dispatchEvent(new Event('input',{bubbles:true}));
            }""")
            page.wait_for_function("""() => {
              const rec=envPending.get('truecolor');
              return rec && rec.successes>0 && rec.requestedDetail && !rec.detailSuccesses;
            }""", timeout=15_000)
            page.evaluate("() => { window.__qaContinuityPending=envPending.get('truecolor'); }")
            before = snapshot(page)
            result["checks"]["before_progress_zero"] = before
            result["assertions"]["fixture_has_no_useful_detail"] = (
                network["transparentLowLod"] > 0 and network["detailAbortedWithoutStatus"] > 0
                and before["candidate"]["successes"] > 0 and before["candidate"]["requestedDetail"]
                and before["candidate"]["detailSuccesses"] == 0
                and before["candidate"]["httpFailures"] == 0 and before["candidate"]["missing"] == 0)

            # Un error de red sin status ya no deja peticiones pendientes. La
            # cola se fija vacía solamente durante check(), sin cambiar app.js.
            page.evaluate("""() => {
              const globe=viewer.scene.globe;
              window.__qaTilesLoadedDescriptor=Object.getOwnPropertyDescriptor(globe,'tilesLoaded');
              Object.defineProperty(globe,'tilesLoaded',{configurable:true,get:()=>true});
              globe.tileLoadProgressEvent.raiseEvent(0);
            }""")
            page.wait_for_timeout(250)
            after_progress = snapshot(page)
            page.evaluate("""() => {
              const globe=viewer.scene.globe, previous=window.__qaTilesLoadedDescriptor;
              if(previous)Object.defineProperty(globe,'tilesLoaded',previous);
              else delete globe.tilesLoaded;
            }""")
            result["checks"]["after_progress_zero"] = after_progress
            result["assertions"]["progress_zero_keeps_previous_image"] = (
                after_progress["sameOld"] and after_progress["oldVisible"] and after_progress["selected"])
            result["assertions"]["progress_zero_keeps_candidate_unready"] = (
                after_progress["pendingSame"] and not after_progress["candidate"]["ready"])

            page.wait_for_function("() => !envPending.has('truecolor')", timeout=23_000)
            after_timeout = snapshot(page)
            result["checks"]["after_18s_timeout"] = after_timeout
            result["assertions"]["timeout_keeps_previous_selected_visible"] = (
                after_timeout["sameOld"] and after_timeout["oldVisible"] and after_timeout["selected"]
                and after_timeout["active"] and after_timeout["failed"])
            result["assertions"]["timeout_does_not_promote_empty_candidate"] = (
                not after_timeout["candidate"]["ready"] and not after_timeout["pending"]
                and after_timeout["elapsedCandidateMs"] >= 17_500)

            help_button = page.locator(".help-button").first
            help_button.focus()
            page.wait_for_function("() => !document.getElementById('ignisHelpPopover').hidden")
            help_button.dispatch_event("pointerenter", {"pointerType": "mouse"})
            help_button.dispatch_event("pointerleave", {"pointerType": "mouse"})
            page.wait_for_timeout(300)
            focused_help = help_button.evaluate("""button => ({
              focused:document.activeElement===button,
              expanded:button.getAttribute('aria-expanded')==='true',
              open:!document.getElementById('ignisHelpPopover').hidden,
            })""")
            result["checks"]["help_after_pointer_leave_with_focus"] = focused_help
            result["assertions"]["focused_help_survives_pointer_leave"] = all(focused_help.values())
            page.locator("#btnPlay").focus()
            page.wait_for_timeout(300)
            moved_focus = help_button.evaluate("""button => ({
              moved:document.activeElement!==button,
              collapsed:button.getAttribute('aria-expanded')==='false',
              closed:document.getElementById('ignisHelpPopover').hidden,
            })""")
            result["checks"]["help_after_focus_moves"] = moved_focus
            result["assertions"]["help_closes_when_focus_moves"] = all(moved_focus.values())
        except Exception as error:
            result["exception"] = f"{type(error).__name__}: {error}"
            result["assertions"]["smoke_completed"] = False
        finally:
            result["network"] = network
            result["pageErrors"] = errors
            result["assertions"]["no_page_errors"] = not errors
            result["passed"] = bool(result["assertions"]) and all(result["assertions"].values())
            browser.close()

    path = args.output / "continuidad_resultados.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "assertions": result["assertions"],
                      "network": network, "exception": result.get("exception"),
                      "pageErrors": errors, "output": str(path)}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
