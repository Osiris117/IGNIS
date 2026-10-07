# IGNIS · Sistema visual v0.9.1 (UI/UX)

Este documento describe el sistema de diseño de IGNIS: **tokens**, los dos temas
(oscuro / claro), el sistema de iconos, foco, movimiento y las **mediciones de
contraste** con las que se valida. Se aplicó el checklist de la skill de UI/UX
(HUD / Sci-Fi FUI, soporte Light + Dark) conservando la identidad verde de IGNIS.

---

## 1. Arquitectura de temas

Un solo punto de verdad: variables CSS en `:root` (tema oscuro) y su sobrescritura
en `html[data-theme="light"]`. Ningún componente define colores propios.

```css
:root{
  --bg:#040806; --text:#e8fff5; --muted:#7d9686; --accent:#8bff6a; ...
  --shadow-rgb:0,0,0;   /* solo sombras           */
  --inset-rgb:0,0,0;    /* superficies internas   */
}
html[data-theme="light"]{
  --bg:#eef4f1; --text:#0b1a12; --muted:#3f6250; --accent:#1a6b35; ...
  --shadow-rgb:11,40,26;  /* sombra verde oscura  */
  --inset-rgb:223,233,227;/* superficie interna clara */
}
```

El conmutador (`static/ui-shell.js`) escribe **`document.documentElement.dataset.theme`**
y expone `window.IGNIS_APPLY_THEME(theme)` (Cesium) y `window.IGNIS_RERENDER()`
(colores calculados en JS: estados de evento, severidad, retícula de calor).

### 1.1 Incidencias corregidas (v0.9.1)

| Síntoma | Causa raíz | Corrección |
|---|---|---|
| El modo claro "no cambiaba": paneles y microcopy seguían oscuros | `transition:all .16s` en los botones: al conmutar, el navegador dejaba el color **a medio interpolar** y no lo recomputaba | Transiciones declaradas por propiedad (color, border-color, background-color, box-shadow, transform, opacity) + clase `html.theme-switching` que desactiva animaciones durante el cambio |
| El **calendario** y el gestor de archivo se veían oscuros en claro | Se usaba `--shadow-rgb` (verde oscuro) como **color de fondo** (`background:rgba(var(--shadow-rgb),.32)`) | Token propio `--inset-rgb` para superficies internas; `--shadow-rgb` queda solo para sombras |
| El color del estado (`DECLINING`, …) se quedaba en el valor del tema anterior | El color se asignaba una vez al abrir el dossier y no se recomputaba | `IGNIS_RERENDER()` reasigna el color leyendo la paleta del tema activo (pasos protegidos con `try`) |
| Celdas de calendario con contraste insuficiente (3.05–4.29:1) | Rellenos translúcidos sobre la superficie oscura + contadores a `opacity:.62` | Escala térmica aclarada en claro, contadores a `opacity:.85`, anillo interior para `level-extreme` |

## 2. Paletas

| Token | Oscuro | Claro | Uso |
|---|---|---|---|
| `--bg` / `--bg-deep` | `#040806` / `#020504` | `#eef4f1` / `#e6efeb` | Fondo de aplicación |
| `--text` / `--text-2` / `--text-3` | `#e8fff5` / `#c2e0d2` / `#9db9ab` | `#0b1a12` / `#22402f` / `#2c4a38` | Texto |
| `--muted` / `--muted-2` / `--muted-3` | `#7d9686` / `#7d9686` / `#6d8579` | `#3f6250` / `#456954` / `#547260` | Microcopy |
| `--accent` / `--accent2` | `#8bff6a` / `#46ffd2` | `#1a6b35` / `#0a6b5c` | Acento, acciones |
| `--yellow` / `--orange` / `--red` | `#ffdc6a` / `#ff9e42` / `#ff4e36` | `#7a6000` / `#a34c07` / `#b91c1c` | Actividad / alertas |

Colores de estado por tema (en `static/app.js`, leídos con `pal()`):

| Estado | Oscuro | Claro |
|---|---|---|
| EMERGING | `#ffdc6a` | `#8a6d00` |
| EXPANDING | `#ff9e42` | `#b45309` |
| STABLE | `#a6ff77` | `#1f7a3d` |
| DECLINING | `#46ffd2` | `#0b7a68` |
| EXTINCT | `#789184` | `#547260` |
| CRITICAL | `#ff4e36` | `#b91c1c` |

## 3. Iconos (sin emojis)

9 iconos SVG en línea (`viewBox 24`, `stroke:currentColor`, 13 px, clase `.ico`):
tema sol/luna, chevron de colapso, cierre (×), frames (‹ ›), reproducir, detener.
Todos los botones llevan `aria-label`; `#themeToggle` expone `aria-pressed` y el
nombre accesible cambia con el tema ("Activar modo claro" / "Activar modo oscuro").

## 4. Accesibilidad

- **Foco visible**: `:focus-visible{outline:2px solid var(--accent2);outline-offset:2px}`.
- **Cursor**: `cursor:pointer` explícito en botones, segmentos, celdas, chips y filas.
- **Contraste objetivo**: AA — 4.5:1 texto normal, 3:1 texto grande (≥24 px, o ≥18.66 px en negrita).
- **Chips y etiquetas**: `white-space:nowrap` (nunca se parten en dos líneas).
- **Movimiento**: `@media (prefers-reduced-motion: reduce)` oculta la línea de
  barrido (`.scanline`) y acorta transiciones.
- **Selección**: `::selection` con el acento del tema activo.
- **Responsive**: 1440 / 1024 / 760 px (paneles laterales colapsan, rejillas a una columna).

## 5. Método de verificación de contraste

Auditoría automatizada (`Playwright` + CDP) sobre el **iframe del preview**
(`sandbox="allow-scripts"`, el mismo entorno que ve el usuario):

1. Carga DEMO FUSIÓN, abre el panel del analista y un evento (`openTrack`).
2. Evalúa contraste WCAG del texto **sobre el fondo efectivo** (cadena de
   `background-color` con composición alfa).
3. Detecta **superficies oscuras en modo claro** (lum < 0.22 en áreas > 4000 px²).
4. Alterna el tema y repite; después abre **calendario**, **archivo**, **briefing** y **aviso (toast)**.
5. **Verificación por píxel**: captura PNG y muestreo de píxeles reales en las
   celdas del calendario para validar el modelo de composición
   (desvío observado ≤ 3/255 por canal).

Resultado v0.9.1 (5 estados × 2 comprobaciones): **0 fallos de contraste,
0 superficies con tema equivocado, 0 errores de JavaScript**.

Leyenda de celdas (calendario) en claro: `low .09` → `moderate .18` → `high .28`
→ `very-high .40` → `extreme .48 + anillo interior`, todos con texto oscuro y
contadores a `opacity:.85` (≥4.5:1 medido por píxel).
