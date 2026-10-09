#!/usr/bin/env python3
"""Regresión de idioma del dossier y panel analista (respuestas API controladas)."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000/')
    parser.add_argument('--output', type=Path, default=Path('/tmp/ignis-ui-verificado'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--use-gl=swiftshader', '--enable-unsafe-swiftshader'])
        c = b.new_context(viewport={'width': 1600, 'height': 900}, locale='es-MX')
        c.route('https://**/*', lambda r: r.abort())
        c.route('**/api/gibs/**', lambda r: r.fulfill(status=502, body='offline'))
        def environment(route):
            lang = parse_qs(urlsplit(route.request.url).query).get('lang', ['es'])[0]
            label = 'SECO' if lang == 'es' else 'DRY'
            route.fulfill(json={'drought': {'available': True, 'category_label': label, 'percentile': 20, 'evidence': [label]}})
        c.route('**/api/environment/intelligence?**', environment)
        def briefing(route):
            payload = route.request.post_data_json
            lang = payload['lang']
            route.fulfill(json={'track_id': payload['track']['id'], 'lang': lang,
                'headline': 'INFORME' if lang == 'es' else 'BRIEFING', 'sentences': [], 'scores': {}, 'caveats': []})
        c.route('**/api/analyst/briefing', briefing)
        page = c.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(args.url, wait_until='domcontentloaded')
        page.wait_for_function("() => typeof evolutionTracks !== 'undefined' && evolutionTracks.length > 0")
        page.evaluate("openTrack(evolutionTracks.find(t => t.status === 'EXPANDING') || evolutionTracks[0])")
        page.wait_for_function("() => document.getElementById('envDrought').textContent.includes('SECO')")
        page.evaluate("document.querySelector('#langSwitch [data-lang=en]').click()")
        page.wait_for_function("() => document.getElementById('envDrought').textContent.includes('DRY')")
        result = page.evaluate("""() => ({
            dossierEn: document.getElementById('detailSeverity').textContent,
            analystRemainsClosed: document.getElementById('analystPanel').classList.contains('hidden'),
            environmentEn: document.getElementById('envDrought').textContent,
        })""")
        page.screenshot(path=str(args.output / 'dossier_en_verificado.png'))
        page.evaluate("document.getElementById('themeToggle').click()")
        result['themeAriaEn'] = page.locator('#themeToggle').get_attribute('aria-label')
        page.evaluate("IGNIS_ANALYST.load(selectedTrack)")
        page.wait_for_function("() => document.getElementById('analystHeadline').textContent === 'BRIEFING'")
        page.evaluate("document.querySelector('#langSwitch [data-lang=es]').click()")
        page.wait_for_function("() => document.getElementById('analystHeadline').textContent === 'INFORME'")
        page.wait_for_function("() => document.getElementById('envDrought').textContent.includes('SECO')")
        result['openBriefingLocalized'] = True
        page.evaluate("IGNIS_ANALYST.close(); document.querySelector('#langSwitch [data-lang=en]').click()")
        result['closedBriefingStaysClosed'] = page.locator('#analystPanel').evaluate("e => e.classList.contains('hidden')")
        result['errors'] = errors
        result['passed'] = (result['dossierEn'] == 'EXPANDING' and result['analystRemainsClosed']
            and result['themeAriaEn'] == 'Dark mode' and result['openBriefingLocalized']
            and result['closedBriefingStaysClosed'] and not errors)
        b.close()
    (args.output / 'idioma_resultados.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
