#!/usr/bin/env python3
"""Comprueba ayudas accesibles ES/EN con teselas controladas, sin NASA."""
import argparse
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from ui_timeline_audit import fixture_png


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8000/')
    parser.add_argument('--output',type=Path,default=Path('/tmp/ignis-ui-correcciones'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    result={'assertions':{},'errors':[],'input':'physical mouse and keyboard; synthetic imagery'}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--use-gl=swiftshader','--enable-unsafe-swiftshader'])
        context=browser.new_context(viewport={'width':1600,'height':900},locale='es-MX')
        png=fixture_png()
        context.route('https://**/*',lambda route: route.fulfill(content_type='image/png',body=png))
        context.route('**/api/gibs/**',lambda route: route.fulfill(content_type='image/png',body=png))
        page=context.new_page();page.on('pageerror',lambda e: result['errors'].append(str(e)))
        try:
            page.goto(args.url,wait_until='domcontentloaded')
            page.wait_for_function("() => frames.length > 1 && document.querySelectorAll('.help-button').length > 20")
            page.wait_for_timeout(5500)
            page.wait_for_function("() => envPending.size === 0 && viewer.scene.globe.tilesLoaded", timeout=20000)
            page.wait_for_timeout(600)
            result['idle']=page.evaluate("""() => new Promise(resolve => {
              let renders=0,updates=0;
              const removeRender=viewer.scene.postRender.addEventListener(()=>renders++);
              const removeUpdate=viewer.scene.postUpdate.addEventListener(()=>updates++);
              setTimeout(()=>{removeRender();removeUpdate();resolve({renders,updates,window_ms:6500});},6500);
            })""")
            result['assertions']['idle_avoids_unnecessary_redraw']=result['idle']['renders']<=1 and result['idle']['updates']>0
            button=page.locator('.help-button[data-help-key="modes"]').first
            button.hover(force=True)
            page.wait_for_selector('#ignisHelpPopover:visible')
            result['assertions']['hover_explains']=bool(page.locator('#ignisHelpBody').inner_text().strip())
            started=time.perf_counter();button.click(force=True,timeout=10000)
            result['physical_click_ms']=round((time.perf_counter()-started)*1000)
            page.mouse.move(800,100);page.wait_for_timeout(300)
            result['assertions']['click_pins_help']=page.locator('#ignisHelpPopover').is_visible()
            result['assertions']['button_accessible']=button.get_attribute('aria-expanded')=='true' and bool(button.get_attribute('aria-label'))
            page.screenshot(path=str(args.output/'ayuda_es.png'))
            page.keyboard.press('Escape')
            result['assertions']['escape_closes']=not page.locator('#ignisHelpPopover').is_visible()
            button.focus();page.keyboard.press('Enter')
            result['assertions']['keyboard_opens']=page.locator('#ignisHelpPopover').is_visible()
            page.locator('.lang-btn[data-lang="en"]').evaluate('x=>x.click()')
            result['assertions']['help_translates_open']=page.locator('#ignisHelpTitle').inner_text()=='Map modes'
            result['assertions']['demo_origin_visible']='DEMONSTRATION' in page.locator('#dataOriginNote').inner_text()
            page.screenshot(path=str(args.output/'ayuda_en.png'))
            # Abrir ayuda junto al borde y verificar que el texto sigue dentro del viewport.
            page.keyboard.press('Escape')
            page.set_viewport_size({'width':420,'height':800})
            mobile_help=page.locator('.timeline > .help-button')
            mobile_help.click(force=True,timeout=10000)
            result['assertions']['mobile_timeline_help_opens']=page.locator('#ignisHelpPopover').is_visible()
            bounds=page.locator('#ignisHelpPopover').bounding_box()
            result['assertions']['narrow_viewport_no_overflow']=bool(bounds and bounds['x']>=0 and bounds['x']+bounds['width']<=421 and bounds['y']>=0 and bounds['y']+bounds['height']<=801)
            result['help_buttons']=page.locator('.help-button').count()
            result['assertions']['all_help_named']=page.locator('.help-button').evaluate_all("xs=>xs.every(x=>x.getAttribute('aria-label') && x.getAttribute('aria-controls'))")
        except Exception as error:
            result['exception']=str(error);result['assertions']['completed']=False
            result['diagnostic']=page.evaluate("() => ({pending:[...envPending.keys()],records:Object.fromEntries(Object.entries(envLayers).map(([k,r])=>[k,{successes:r.successes,ready:r.ready,date:r.date}])),tilesLoaded:viewer.scene.globe.tilesLoaded,frame:viewer.scene.frameState.frameNumber,renderLoop:viewer.useDefaultRenderLoop,alerts:document.getElementById('renderAlert').className})")
        result['assertions']['no_page_errors']=not result['errors']
        result['passed']=all(result['assertions'].values())
        browser.close()
    (args.output/'ayuda_resultados.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
