/* ==========================================================================
   IGNIS v0.9 — Shell de la interfaz
   1) Selector de idioma ES/EN  ·  2) Modo claro / oscuro
   3) Panel del INTELLIGENCE ANALYST (narrativa con citas numéricas)
   Se carga antes de app.js: sólo usa el DOM y window.IGNIS_I18N.
   ========================================================================== */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const I18N = window.IGNIS_I18N;

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { /* origen opaco */ }
  }
  function read(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }

  /* ----------------------------------------------------------------------- */
  /* 1 · Tema claro / oscuro                                                 */
  /* ----------------------------------------------------------------------- */
  const THEME_KEY = 'ignis-theme';
  let theme = read(THEME_KEY) || 'dark';

  function applyTheme(next) {
    theme = next === 'light' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    document.body.classList.toggle('theme-light', theme === 'light');
    const btn = $('themeToggle');
    if (btn) {
      btn.classList.toggle('on', theme === 'light');
      btn.querySelector('.theme-icon').textContent = theme === 'light' ? '☀' : '☾';
      btn.title = theme === 'light'
        ? (I18N.lang === 'es' ? 'Cambiar a modo oscuro' : 'Switch to dark mode')
        : (I18N.lang === 'es' ? 'Cambiar a modo claro' : 'Switch to light mode');
    }
    store(THEME_KEY, theme);
    // Cesium necesita un empujón para reajustar el contraste del globo.
    if (window.IGNIS_APPLY_THEME) { try { window.IGNIS_APPLY_THEME(theme); } catch (e) {} }
  }

  $('themeToggle') && $('themeToggle').addEventListener('click', () => {
    applyTheme(theme === 'light' ? 'dark' : 'light');
  });

  /* ----------------------------------------------------------------------- */
  /* 2 · Idioma                                                              */
  /* ----------------------------------------------------------------------- */
  function applyLang(next) {
    I18N.apply(next);
    document.querySelectorAll('.lang-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.lang === I18N.lang);
    });
    applyTheme(theme); // refresca el tooltip del botón de tema
  }

  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => applyLang(btn.dataset.lang));
  });

  I18N.onChange(() => {
    // Al cambiar de idioma, los textos dinámicos ya pintados se vuelven a generar.
    if (window.IGNIS_RERENDER) { try { window.IGNIS_RERENDER(); } catch (e) {} }
    if (window.IGNIS_ANALYST && window.IGNIS_ANALYST.lastTrack) {
      window.IGNIS_ANALYST.load(window.IGNIS_ANALYST.lastTrack, { silent: true });
    }
  });

  /* ----------------------------------------------------------------------- */
  /* 3 · Analista de inteligencia                                            */
  /* ----------------------------------------------------------------------- */
  function apiBase() { return ''; }   // mismo origen: /api/... vía el proxy del servidor

  async function fetchBriefing(track) {
    const response = await fetch(apiBase() + '/api/analyst/briefing', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        track,
        lang: I18N.lang,
        environment: true,
        baseline: true,
      }),
    });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  }

  function indexBar(label, value, cls) {
    if (value === null || value === undefined) {
      return `<div class="idx"><span>${label}</span><div class="idx-track"><i class="idx-fill ${cls}" style="width:0"></i></div><strong>—</strong></div>`;
    }
    return `<div class="idx"><span>${label}</span><div class="idx-track"><i class="idx-fill ${cls}" style="width:${Math.max(2, value)}%"></i></div><strong>${value}</strong></div>`;
  }

  function renderBriefing(data) {
    const T = I18N.t.bind(I18N);
    const kicker = $('analystKicker');
    if (kicker) kicker.textContent = T('INTELLIGENCE ANALYST · BRIEFING');
    const copyBtn = $('btnAnalystCopy');
    if (copyBtn) copyBtn.textContent = T('COPY');
    $('analystTrack').textContent = data.track_id || '—';
    $('analystMeta').textContent = [
      data.status,
      data.generated_at ? data.generated_at.replace('T', ' ').replace('Z', ' UTC') : null,
      data.lang ? data.lang.toUpperCase() : null,
    ].filter(Boolean).join(' · ');
    $('analystHeadline').textContent = data.headline || '';

    const scores = data.scores || {};
    $('analystIndices').innerHTML = [
      indexBar(T('short_dryness'), scores.dryness_index, 'dry'),
      indexBar(T('short_fuel'), scores.fuel_index, 'fuel'),
      indexBar(T('short_smoke'), scores.smoke_index, 'smoke'),
      indexBar(T('short_context'), scores.environmental_context_index, 'ctx'),
    ].join('');

    const BLOCK_TAG = {
      activity: 'ACT', sensors: 'SENS', motion: 'DRIFT', environment: 'ENV',
      baseline: 'HIST', confidence: 'CONF', uncertainty: 'UNC',
    };
    const html = (data.sentences || []).map(s => {
      const cites = (s.citations || []).filter(c => c.value !== null && c.value !== undefined);
      const chips = cites.map(c =>
        `<span class="cite"><b>${c.metric}</b> ${typeof c.value === 'number' ? Math.round(c.value * 100) / 100 : c.value}${c.unit ? ' ' + c.unit : ''}<em>${c.source || ''}</em></span>`
      ).join('');
      return `<div class="bline block-${s.block}">
        <span class="btag">${BLOCK_TAG[s.block] || s.block.toUpperCase().slice(0, 4)}</span>
        <p>${s.text}</p>
        ${chips ? `<div class="cites">${chips}</div>` : ''}
      </div>`;
    }).join('');
    $('analystBody').innerHTML = html;

    const caveats = (data.caveats || []).map(c => `<li>${c}</li>`).join('');
    $('analystFoot').innerHTML = `<div class="analyst-method">${data.method || ''}</div><ul>${caveats}</ul>`;
  }

  const Analyst = {
    lastTrack: null,
    open() {
      if ($('analystPanel')) $('analystPanel').classList.remove('hidden');
      document.body.classList.add('analyst-open');   // el banner de seguimiento se aparta
    },
    close() {
      if ($('analystPanel')) $('analystPanel').classList.add('hidden');
      document.body.classList.remove('analyst-open');
    },
    async load(track, opts) {
      if (!track || !track.id) return;
      Analyst.lastTrack = track;
      const silent = opts && opts.silent;
      Analyst.open();
      if (!silent) {
        $('analystTrack').textContent = track.id;
        $('analystHeadline').textContent = I18N.t('analyst_loading');
        $('analystMeta').textContent = '—';
        $('analystIndices').innerHTML = '';
        $('analystBody').innerHTML = '';
        $('analystFoot').innerHTML = '';
      }
      try {
        const data = await fetchBriefing(track);
        renderBriefing(data);
        const citations = (data.sentences || []).reduce((n, s) => n + (s.citations || []).filter(c => c.value !== null && c.value !== undefined).length, 0);
        if (!silent && window.showToast) {
          window.showToast(I18N.t('toast_briefing_done', (data.sentences || []).length, citations), 4600);
        }
      } catch (error) {
        $('analystHeadline').textContent = I18N.t('No briefing data') + ' — ' + error.message;
        if (!silent && window.showToast) window.showToast(I18N.t('toast_briefing_fail', error.message), 6000);
      }
    },
  };
  window.IGNIS_ANALYST = Analyst;

  $('btnAnalyst') && $('btnAnalyst').addEventListener('click', async () => {
    if (Analyst.lastTrack) { Analyst.load(Analyst.lastTrack); return; }
    // Sin selección previa: se pide un ejemplo al backend.
    try {
      const response = await fetch('/api/analyst/sample?lang=' + I18N.lang);
      const payload = await response.json();
      if (payload && payload.track) Analyst.load(payload.track);
    } catch (error) {
      if (window.showToast) window.showToast(I18N.t('toast_briefing_fail', error.message), 6000);
    }
  });
  $('btnAnalystClose') && $('btnAnalystClose').addEventListener('click', Analyst.close);
  $('btnAnalystCopy') && $('btnAnalystCopy').addEventListener('click', async () => {
    const text = $('analystPanel') ? $('analystPanel').innerText : '';
    try {
      await navigator.clipboard.writeText(text);
      if (window.showToast) window.showToast(I18N.t('Copied to clipboard.'), 3000);
    } catch (error) {
      if (window.showToast) window.showToast('Clipboard: ' + error.message, 4000);
    }
  });

  /* ----------------------------------------------------------------------- */
  /* 4 · Arranque                                                            */
  /* ----------------------------------------------------------------------- */
  function boot() {
    applyTheme(theme);
    applyLang(I18N.detect());
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
