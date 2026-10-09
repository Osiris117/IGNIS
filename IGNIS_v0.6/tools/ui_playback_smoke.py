#!/usr/bin/env python3
"""Reproducción con entrada física e imágenes GIBS reales en SwiftShader."""
import argparse,json,time
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8000/')
    parser.add_argument('--output',type=Path,default=Path('/tmp/ignis-ui-correcciones-real'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    result={'assertions':{},'errors':[],'physical_clicks':[]}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader'])
        page=browser.new_page(viewport={'width':1600,'height':900},locale='es-MX')
        page.on('pageerror',lambda e:result['errors'].append(str(e)))
        def click(selector):
            started=time.perf_counter();page.locator(selector).click(force=True,timeout=15000)
            result['physical_clicks'].append({'selector':selector,'elapsed_ms':round((time.perf_counter()-started)*1000)})
        try:
            page.goto(args.url,wait_until='domcontentloaded')
            page.wait_for_function('() => frames.length > 1 && envLayers.truecolor',timeout=30000)
            page.wait_for_timeout(10000)
            page.wait_for_function('() => envPending.size === 0',timeout=20000)
            result['assertions']['server_date_matches_picker']=page.evaluate("() => !!config.current_date && document.getElementById('historyDate').max === config.current_date && document.getElementById('historyDate').value <= config.current_date")
            result['assertions']['software_effects_off']=page.evaluate('() => IGNIS_SOFT && !viewer.scene.orderIndependentTranslucency && !viewer.scene.globe.showGroundAtmosphere && !viewer.scene.highDynamicRange && viewer.resolutionScale === 1')
            click('.section-title .help-button[data-help-key="modes"]')
            page.evaluate('viewer.scene.requestRender()')
            page.screenshot(path=str(args.output/'ayuda_real.png'),timeout=45000)
            page.keyboard.press('Escape')
            for key in ('aerosol','pyro'):
                click(f'.env-chip[data-env="{key}"]')
            page.wait_for_function('() => envPending.size === 0',timeout=20000)
            page.evaluate("""() => {
              window.__playCamera=Cesium.Cartesian3.clone(viewer.camera.positionWC);
              window.__playLayer=envLayers.truecolor.layers[0];window.__playDate=currentEnvDate();
            }""")
            click('#btnPlay')
            page.wait_for_function('() => currentEnvDate() !== window.__playDate',timeout=15000)
            result['assertions']['play_keeps_imagery']=page.evaluate('() => envLayers.truecolor.layers[0] === window.__playLayer')
            result['assertions']['play_keeps_camera']=page.evaluate('() => Cesium.Cartesian3.distance(viewer.camera.positionWC,window.__playCamera) < .001')
            click('#btnPlay')
            result['assertions']['pause_stops']=page.evaluate('() => !playTimer')
            click('#btnPlay')
            result['assertions']['resume_runs']=page.evaluate('() => !!playTimer')
            click('#btnPlay')
            page.wait_for_function('() => envPending.size === 0',timeout=20000)
            result['assertions']['selection_persists']=page.evaluate("() => ['truecolor','aerosol','pyro'].every(k => envSelections.has(k) && document.querySelector(`[data-env=\"${k}\"]`).getAttribute('aria-pressed') === 'true')")
            result['state']=page.evaluate("() => ({date:currentEnvDate(),referenceDate:envLayers.truecolor?.topDate,visibleLayers:Array.from({length:viewer.imageryLayers.length},(_,i)=>viewer.imageryLayers.get(i)).filter(l=>l.show).length,renderLoop:viewer.useDefaultRenderLoop})")
        except Exception as error:
            result['exception']=str(error);result['assertions']['completed']=False
        result['assertions']['no_page_errors']=not result['errors']
        result['passed']=all(result['assertions'].values());browser.close()
    (args.output/'reproduccion_real_resultados.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
