# Sistema de diseño — Cuadra

Estética **minimalista** (tipo Linear): superficie oscura profunda, un solo acento índigo,
tipografía Inter, bordes redondeados sutiles y micro-animaciones. Todo lo
documentado acá proviene de los tokens reales del proyecto.

Fuentes de verdad (no duplicar valores, citar):
- Tokens Tailwind (Tailwind 4, sin `tailwind.config.js`): bloque `@theme` de `frontend/src/styles/index.css`; paleta por defecto fijada a los hex de Tailwind 3 en `frontend/src/styles/paleta-tailwind3.css`
- Estilos base + clases de componente: `frontend/src/styles/index.css`
- Paleta de marca de la landing (variables CSS): `frontend/src/components/landing/LandingStyles.tsx`

Documento relacionado: convenciones de UX (tema, PWA, lock, toasts, paginación)
en [UX_RULES.md](./UX_RULES.md).

---

## 1. Principios

- **Contraste suave**: jerarquía por contraste suave, no por bordes pesados;
  cards con sombra mínima en light y sin sombra en dark.
- **Un solo acento en los dos temas**: índigo `--ml-accent` (`#5E6AD2` claro /
  `#818CF8` oscuro, fondo oscuro `#0B0B0F`). Verde y rojo solo con significado
  (ingresos/egresos, OK/error). Misma tipografía en los dos temas.
- **Mobile-first**: ver [UX_RULES.md](./UX_RULES.md) sección 3.

---

## 2. Paleta de color

### Tokens de la app (`@theme` en `frontend/src/styles/index.css`, prefijo `ml-`)

**Light mode**
| Token | Hex | Uso |
|---|---|---|
| `ml-blue` | `#5E6AD2` | primario light (botones, links activos) |
| `ml-blue-dark` | `#4A55BE` | hover primario |
| `ml-blue-darker` | `#3A43A0` | bordes de header de tabla |
| `ml-gray` | `#E4E4E7` | bordes |
| `ml-gray-dark` | `#A1A1AA` | bordes/íconos atenuados |
| `ml-gray-bg` | `#F4F4F5` | fondo de página |
| `ml-text` | `#18181B` | texto principal |
| `ml-text-soft` | `#71717A` | texto secundario |
| `ml-yellow` / `ml-yellow-dark` | `#FFE600` / `#F5DC00` | acento legacy |

**Dark mode**
| Token | Hex | Uso |
|---|---|---|
| `ml-dark-bg` | `#0B0B0F` | fondo de página (= `theme_color` del manifest) |
| `ml-dark-surface` | `#111116` | superficies (sidebar, cards) |
| `ml-dark-card` | `#16161C` | cards/inputs |
| `ml-dark-border` | `#1E1E26` | bordes |
| `ml-dark-hover` | `#1A1A22` | hover |

**Acento (único, mode-aware)** — oct 2026

La app autenticada tiene **un solo color de acento**: el índigo tipo Linear.
Se define con variables CSS en `index.css` (canales "R G B", soportan opacidad
como `bg-ml-accent/10`) y Tailwind lo expone como `ml-accent`:

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `ml-accent` (vía `--ml-accent`) | `#5E6AD2` | `#818CF8` | fondo de botón primario, nav activa, segmented control activo, foco de inputs, links, línea de gráficos, logo |
| `ml-accent-hover` (vía `--ml-accent-hover`) | `#4A55BE` | `#A5B4FC` | hover del botón primario |
| `ml-accent-fg` (vía `--ml-accent-fg`) | `#FFFFFF` | `#0B0B0F` | texto sobre el acento |

En oscuro el acento es más claro para leerse sobre `#0B0B0F` (≈6.6:1) y lleva
texto oscuro encima. Patrón de uso: selección = `bg-ml-accent/10 text-ml-accent`;
control activo / botón = `bg-ml-accent text-ml-accent-fg hover:bg-ml-accent-hover`.
`ml-blue` (`#5E6AD2`) es el valor claro del acento y sigue en muchos `bg-ml-blue`;
en oscuro `text-ml-blue` se remapea al acento claro (override en `index.css`).
Las clases `btn-primary` y `btn-yellow` son el mismo botón de acento
(`btn-yellow` conserva el nombre histórico; no renombrar en masa).

**Verde y rojo: solo semánticos**

El verde ya no es acento ni "color de marca" en la UI. Verde y rojo se usan
**únicamente con significado**: plata que entra / sale (ingresos/egresos),
éxito / error, badges OK/conciliado vs error, progreso completado. Nada de
verde para navegación, botones primarios, foco, títulos o montos neutros
(`.monto` ya no se pinta de verde en oscuro). En gráficos: líneas en el acento
(o neutras) y verde/rojo solo cuando la serie significa ingresos/egresos
(ej. barras de Flujo de Caja). Un dato en 0 no lleva color semántico.

`ml-green` y `status-ok` son **mode-aware** vía la variable CSS `--ml-green`:
legible en claro y brillante en oscuro. Los demás tokens verde son fijos.

| Token | Claro | Oscuro |
|---|---|---|
| `ml-green` (vía `--ml-green`) | `#16A34A` | `#4ADE80` |
| `ml-green-bright` | `#4ADE80` | `#4ADE80` |
| `ml-green-dim` | `#16A34A` | `#16A34A` |
| `ml-green-muted` | `#14532D` | `#14532D` |

El logo de marca (`CuadraLogo`) y los íconos PWA (`icon-192/512.svg` y sus PNG en
`public/icons/`, más `apple-touch-icon.png`) van siempre sobre placa oscura: arco
violeta `#818CF8` con punto `#E4E4E7` (nov 2026, antes verde). El favicon es la placa
violeta `#5E6AD2` con ✓ blanco (mejor contraste a 16px), la misma marca que usa la landing.
El wordmark "Cuadra" va en el color de texto (Inter semibold, `tracking-tight`) y el header
del sidebar es la misma superficie que el sidebar (sin banda negra).

**Estados semánticos** (`colors.status`)
| Token | Hex |
|---|---|
| `status-ok` | mode-aware vía `--ml-green` (claro `#16A34A` / oscuro `#4ADE80`) |
| `status-error` | `#EF4444` |
| `status-warn` | `#F59E0B` |
| `status-info` | `#5E6AD2` |
| `status-neutral` | `#71717A` |

Regla práctica: **primario** = `ml-accent` en los dos temas (ver `.btn-primary`).
Botones secundarios / exportar (Excel, .xlsx) van neutros (borde `ml-gray`), no
en verde.

### Paleta de marca de la landing (`LandingStyles.tsx`, variables CSS)

La landing pública (`/` sin sesión y `/landing`) usa su propio set de variables
CSS bajo `.landing-root`, con valores light/dark independientes. **Nada de la
landing toca los tokens globales de la app** (ni al revés): las clases de la
landing llevan prefijo `l-` (`.l-btn`, `.l-h1`, `.l-section`…) y `hd-` (demo del
hero), así que ya no chocan con `.btn-ghost`/`.btn-primary` de la app.
- Acento de marca violeta, los mismos valores que la app (nov 2026):
  light `--accent: #5E6AD2` (hover `#4A55BE`, texto blanco), texto de acento `#4A55BE`;
  dark `--accent: #818CF8` (hover `#A5B4FC`, texto `#0B0B0F`), texto de acento `#A5B4FC`.
- Verde solo como estado de éxito: `--ok*` (`#16A34A` / `#4ADE80`) en "Acreditado",
  filas conciliadas, Control del banco ✓ y barras de planilla completas.
- Ámbar de "revisar": `--amber` (`#B45309` / `#FBBF24`).
- Marca: placa `#5E6AD2` con ✓ blanco (igual en los dos temas, igual que `favicon.svg`).
- El bloque final de pedido de demo es un degradé índigo casi negro
  (`#1A1B3A → #0B0B0F`) en los dos temas.

**Tipografía de la landing** (oct 2026): solo Inter (titulares 700 con tracking
`-0.04em`/`-0.048em`) + JetBrains Mono para importes (`.num`). Las dos ya vienen
de `index.html`: la landing no baja fuentes extra (antes sumaba Fraunces y
Cormorant Garamond italic, que se sacaron por "template").

**Movimiento**: solo `opacity`/`transform`. Reveals al hacer scroll con
`useReveal`/`<Reveal>` (`shared.tsx`), demo del hero (`HeroDemo.tsx`) en loop solo
mientras está en pantalla. Con `prefers-reduced-motion` todo queda en el estado
final sin transiciones.

---

## 3. Tipografía

Definida en el `@theme` de
`frontend/src/styles/index.css`.

- **Sans (UI)**: `Inter` (fallback `-apple-system, BlinkMacSystemFont, Segoe UI`).
  Pesos cargados: 400 / 500 / 600 / 700.
- **Mono**: `JetBrains Mono` (fallback `Fira Code, Consolas`). Pesos 400 / 500.
  Se usa para montos en tablas (`.monto`) y códigos. Las fuentes no cambian
  entre temas: `kpi-value` y `th-macro` ya no pasan a mono en oscuro (KPIs en
  Inter con `tabular-nums`), y el wordmark va en Inter.
- Tamaño extra: `text-2xs` = `10px / 14px` (badges, labels, KPI labels).
- Antialiasing `-webkit-font-smoothing: antialiased` en `body`.

Regla: **valores numéricos/financieros van en mono con `tabular-nums`** (clase
`.monto`), para alineación de columnas.

---

## 4. Espaciado, radios, sombras, animaciones

(`@theme` en `frontend/src/styles/index.css`)

- **Border radius**: `xl = 10px`, `2xl = 14px` (cards, inputs, modales).
- **Sombras**:
  - `shadow-card` / `shadow-card-hover` (light).
  - `shadow-green-glow` / `shadow-green-sm`: legacy, la app ya no las usa
    (los botones de acento no llevan glow).
- **Animaciones declaradas**: `animate-slide-in` (drawer), `animate-fade-in`.
- **Animaciones en CSS** (`index.css`): `.drawer-enter` (slide 0.22s),
  `.page-enter` (fade-up 180ms), `.skeleton` (pulse), `.animate-shake` (PIN
  incorrecto en LockScreen), `.toast-enter`.
- **Mobile** (`max-width: 768px`): cards/KPIs con padding reducido y `kpi-value`
  más chico.

---

## 5. Clases de componente (en `@layer components`, `index.css`)

Estas clases encapsulan el estilo de la app y traen sus variantes `dark:`:

| Clase | Propósito |
|---|---|
| `.btn-primary` | botón primario (acento `ml-accent`, mode-aware) |
| `.btn-yellow` | mismo botón primario de acento (nombre histórico) |
| `.btn-secondary` | botón secundario (superficie + borde) |
| `.btn-ghost` | botón sin fondo (acción terciaria) |
| `.card` | contenedor estándar (fondo + borde + sombra) |
| `.input-field` | input/select de texto (focus ring del acento) |
| `.label` | label de formulario (uppercase, tracking) |
| `.badge` + `.badge-ok/warn/error/info/neutral` | estados |
| `.kpi` / `.kpi-value` / `.kpi-label` | tarjetas de métrica del dashboard |
| `.th-macro` | header de tabla estilo Excel Macro |
| `.row-um` | fila de "Últimos Movimientos" (verde tenue) |
| `.row-15` | fila compacta 15px (densidad estilo Excel) |
| `.monto` | número monoespaciado tabular |

Regla: usar estas clases en lugar de repetir cadenas Tailwind; cambios de marca
se hacen en un solo lugar.

---

## 6. Componentes reutilizables clave (`frontend/src/components/`)

| Componente | Archivo | Propósito |
|---|---|---|
| `Layout` | `Layout.tsx` | shell de la app: sidebar desktop + drawer mobile + bottom nav + header con búsqueda ⌘K, campana de alertas y toggle de tema. Monta `Toaster`, `ConfirmDialog`, `AppLockGuard`, `SearchModal`, `AgenteChat` y filtra la navegación por permisos. |
| `PlanillaPanel` | `PlanillaPanel.tsx` | tabla de planilla conciliada: paginación server-side (`PAGE_SIZE=100`), filtros por columna, bulk edit, filas compactas. Ver [UX_RULES.md](./UX_RULES.md) §9. |
| `FileUpload` | `FileUpload.tsx` | input de archivos compacto con drag & drop, single o multi-archivo. |
| `SearchModal` | `SearchModal.tsx` | búsqueda global (⌘K): clientes, planillas, movimientos, cheques; debounce 300ms, mínimo 2 chars. |
| `ConfirmModal` / `ConfirmDialog` | `ConfirmModal.tsx`, `ConfirmDialog.tsx` | modal de confirmación; `ConfirmDialog` conecta `ConfirmModal` al store `confirm.ts` (patrón promesa, soporte `danger`). |
| `Toaster` | `Toaster.tsx` | render de los toasts del store `toast.ts`. |
| `AppLockGuard` / `LockScreen` | `AppLockGuard.tsx`, `LockScreen.tsx` | bloqueo PIN + biometría. Ver [UX_RULES.md](./UX_RULES.md) §4. |
| `ThemeToggle` | `ThemeToggle.tsx` | botón sol/luna (también embebido en `Layout`). |
| `CuadraLogo` | `CuadraLogo.tsx` | logo de marca (con `animate`). |
| `Skeleton` | `Skeleton.tsx` | placeholders de carga (`.skeleton` pulse). |
| `AgenteChat` | `AgenteChat.tsx` | asistente IA flotante (Gemini). |
| `Button` / `Input` | `Button.tsx`, `Input.tsx` | wrappers de los estilos `.btn-*` / `.input-field`. |

### Charts (`frontend/src/components/charts/`)
SVG propios, sin librería externa, con formato `es-AR`:
- `LineChart.tsx` — serie temporal (evolución), interactiva (estado de hover).
- `BarChart.tsx` — barras por serie con color configurable.
- `DonutChart.tsx` — anillo con leyenda y label central; formateo de valor
  configurable (compacto `es-AR` por defecto).

---

## 6bis. Estados vacíos

Un gráfico o tarjeta sin datos no muestra una línea plana en 0 ni barras vacías:
muestra un estado vacío silencioso. `components/charts/ChartEmpty.tsx`:
- `ChartEmpty` — ícono gris + "Todavía no hay movimientos en este período"
  (`CHART_EMPTY_MSG`), borde punteado, mismo alto que el gráfico (el layout no
  salta al llegar los datos).
- `sinDatos(valores)` — `true` si no hay puntos o todos valen 0.
- `LineChart` y `BarChart` lo usan solos (prop `emptyMessage` para otro texto).

Mismo criterio en tarjetas: KPIs en 0 sin verde/rojo (Flujo de Caja), la tabla
de Flujo de Caja con el mismo mensaje, y Control del banco sin extracto ni
transitorias no muestra dos importes en 0. Al agregar un gráfico o tarjeta de
resumen nuevo, reutilizar `ChartEmpty`/`sinDatos`.

## 7. Convenciones de marca menores

- **Nombre visible**: "Cuadra" (el repo y backend conservan el nombre histórico
  "conciliacion-bancaria"). El wordmark va en Inter semibold con el color de
  texto (se quitó `.app-title`, que lo forzaba a verde mono en dark).
- **Scrollbar fina** en dark (4px, thumb `#1E1E26`, hover acento translúcido) —
  `index.css`.
- **Fondo y `color-scheme`**: `.dark` setea `color-scheme: dark` para nativos
  (selects, scrollbars del SO).

---

## Pendiente de revisar

- ~~Colisión de `.btn-ghost`~~ (resuelto oct 2026): la landing ya no define
  `.btn-ghost`; sus clases llevan prefijo `l-`.
- **Capa de compatibilidad Tailwind 3 → 4** (oct 2026, `index.css` +
  `paleta-tailwind3.css`): paleta hex de v3, interlineado fijo de `text-*`,
  `space-y-*` con la semántica de v3, `hover:` sin `@media (hover: hover)`,
  padding 1px en `td/th`, placeholder gris, `cursor: pointer` en botones e
  inputs de fecha sin el reset de v4. Mantiene la app idéntica a v3 (verificado
  con capturas pixel a pixel). Si se agrega un valor nuevo de `space-y-*`, hay
  que sumarlo al bloque de compatibilidad (o usar `flex` + `gap`).
- **Opacidades fuera de la escala de v3** (`white/1`, `/2`, `/3`, `/4`, `/8`,
  `/12` en Cheques, Caja y AgenteChat): con Tailwind 3 esas clases no se
  generaban y en modo oscuro quedaba el fondo claro (cards blancas, botón
  "Importar Excel" ilegible). Tailwind 4 sí las genera, así que ahora se ven
  oscuras como se escribieron.
- **`ml-yellow` / `ml-yellow-dark`** y la clase `.btn-yellow` (hoy el botón de
  acento): nombres legacy del esquema amarillo y después verde; `ml-yellow` ya no
  se usa en la app. Evaluar renombrar `btn-yellow` → `btn-primary` en un PR
  mecánico aparte.
- **`bg-ml-blue text-white`** sigue en muchos lugares: en oscuro queda el índigo
  `#5E6AD2` (un tono más oscuro que `ml-accent` dark `#818CF8`). Mismo color
  de familia, legible; migrar a `bg-ml-accent text-ml-accent-fg` cuando se toque
  cada pantalla.
- **Panel del asistente IA** (`AgenteChat`): siempre oscuro (`#13131A`) con
  `#5E6AD2` fijo, también en modo claro. Es intencional; anotado.
- **Dos paletas de verde** ligeramente distintas conviven: la de la app
  (`ml-green = #22C55E`, `ml-green-dim = #16A34A`) y la de la landing
  (`--ok` = `#16A34A` light / `#4ADE80` dark). Es intencional (la landing
  usa un verde un poco más oscuro en light), pero queda anotado por si se quiere
  unificar.
