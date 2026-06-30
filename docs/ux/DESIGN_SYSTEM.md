# Sistema de diseño — Cuadra

Estética **Linear-inspired**: superficie oscura profunda, acento verde de marca,
tipografía Inter, bordes redondeados sutiles y micro-animaciones. Todo lo
documentado acá proviene de los tokens reales del proyecto.

Fuentes de verdad (no duplicar valores, citar):
- Tokens Tailwind: `frontend/tailwind.config.js`
- Estilos base + clases de componente: `frontend/src/styles/index.css`
- Paleta de marca de la landing (variables CSS): `frontend/src/components/landing/LandingStyles.tsx`

Documento relacionado: convenciones de UX (tema, PWA, lock, toasts, paginación)
en [UX_RULES.md](./UX_RULES.md).

---

## 1. Principios

- **Linear-inspired**: jerarquía por contraste suave, no por bordes pesados;
  cards con sombra mínima en light y sin sombra en dark.
- **Dark mode = identidad de marca**: fondo `#0B0B0F`, acento verde
  fluorescente, números en fuente monoespaciada (estética "hacker/terminal").
  Light mode usa el azul-violeta de Linear (`#5E6AD2`) como primario.
- **Mobile-first**: ver [UX_RULES.md](./UX_RULES.md) sección 3.

---

## 2. Paleta de color

### Tokens de la app (`frontend/tailwind.config.js`, prefijo `ml-`)

**Light mode (Linear light)**
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

**Dark mode (Linear dark)**
| Token | Hex | Uso |
|---|---|---|
| `ml-dark-bg` | `#0B0B0F` | fondo de página (= `theme_color` del manifest) |
| `ml-dark-surface` | `#111116` | superficies (sidebar, cards) |
| `ml-dark-card` | `#16161C` | cards/inputs |
| `ml-dark-border` | `#1E1E26` | bordes |
| `ml-dark-hover` | `#1A1A22` | hover |

**Acento verde (marca, dark)**
| Token | Hex |
|---|---|
| `ml-green` | `#22C55E` |
| `ml-green-bright` | `#4ADE80` |
| `ml-green-dim` | `#16A34A` |
| `ml-green-muted` | `#14532D` |

**Estados semánticos** (`colors.status`)
| Token | Hex |
|---|---|
| `status-ok` | `#22C55E` |
| `status-error` | `#EF4444` |
| `status-warn` | `#F59E0B` |
| `status-info` | `#5E6AD2` |
| `status-neutral` | `#71717A` |

Regla práctica: **primario** = `ml-blue` en light, `ml-green` en dark (ver
`.btn-primary`). El verde de marca aparece en el título de la app, badges OK,
montos y elementos activos en dark.

### Paleta de marca de la landing (`LandingStyles.tsx`, variables CSS)

La landing pública (`/landing`) usa su propio set de variables CSS bajo
`.landing-root`, con valores light/dark independientes. Acentos principales:
- Light: `--accent: #16A34A`, `--accent-2: #15803D`, fondo `#FFFFFF`.
- Dark: `--accent: #22C55E`, `--accent-2: #4ADE80`, fondo `#050508`.
- Texto serif italic de énfasis: `.em-serif` (Cormorant Garamond) en color acento.
- Componentes propios de landing: `.btn-green`, `.btn-ghost`, `.pill`,
  `.wa-btn` (WhatsApp `#25D366`), `.faq-item`, `.compare-table`, etc.

> Nota: la clase utilitaria `.btn-ghost` existe **dos veces** con definiciones
> distintas — una global en `index.css` (Tailwind `@apply`) y otra scoped a
> `.landing-root` en `LandingStyles.tsx`. Ver "Pendiente de revisar".

---

## 3. Tipografía

Definida en `frontend/tailwind.config.js` e importada en
`frontend/src/styles/index.css`.

- **Sans (UI)**: `Inter` (fallback `-apple-system, BlinkMacSystemFont, Segoe UI`).
  Pesos cargados: 400 / 500 / 600 / 700.
- **Mono**: `JetBrains Mono` (fallback `Fira Code, Consolas`). Pesos 400 / 500.
  Se usa para números, montos (`.monto`), KPIs en dark, headers de tabla en dark
  y el título de la app.
- Tamaño extra: `text-2xs` = `10px / 14px` (badges, labels, KPI labels).
- Antialiasing `-webkit-font-smoothing: antialiased` en `body`.

Regla: **valores numéricos/financieros van en mono con `tabular-nums`** (clase
`.monto`), para alineación de columnas.

---

## 4. Espaciado, radios, sombras, animaciones

(`frontend/tailwind.config.js`)

- **Border radius**: `xl = 10px`, `2xl = 14px` (cards, inputs, modales).
- **Sombras**:
  - `shadow-card` / `shadow-card-hover` (light).
  - `shadow-green-glow` / `shadow-green-sm` (glow verde para acentos en dark).
- **Animaciones declaradas**: `animate-slide-in` (drawer), `animate-fade-in`.
- **Animaciones en CSS** (`index.css`): `.drawer-enter` (slide 0.22s),
  `.page-enter` (fade-up 180ms), `.skeleton` (pulse), `.animate-shake` (PIN
  incorrecto en LockScreen), `.toast-enter`.
- **Mobile** (`max-width: 768px`): cards/KPIs con padding reducido y `kpi-value`
  más chico.

---

## 5. Clases de componente (en `@layer components`, `index.css`)

Estas clases encapsulan el estilo Linear y traen sus variantes `dark:`:

| Clase | Propósito |
|---|---|
| `.btn-primary` | botón primario (azul en light, verde en dark) |
| `.btn-yellow` | botón verde fluorescente (igual en light y dark) |
| `.btn-secondary` | botón secundario (superficie + borde) |
| `.btn-ghost` | botón sin fondo (acción terciaria) |
| `.card` | contenedor estándar (fondo + borde + sombra) |
| `.input-field` | input/select de texto (focus ring azul/verde) |
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

## 7. Convenciones de marca menores

- **Nombre visible**: "Cuadra" (el repo y backend conservan el nombre histórico
  "conciliacion-bancaria"). El título en la UI usa fuente mono y color verde
  (`#22C55E`) vía `.app-title` (en dark se fuerza verde con `!important`).
- **Scrollbar fina** en dark (4px, thumb `#1E1E26`, hover verde translúcido) —
  `index.css`.
- **Fondo y `color-scheme`**: `.dark` setea `color-scheme: dark` para nativos
  (selects, scrollbars del SO).

---

## Pendiente de revisar

- **Colisión de `.btn-ghost`**: definida con dos estilos distintos (global en
  `index.css` con `@apply`, y scoped a `.landing-root` en `LandingStyles.tsx`).
  Dentro de la landing gana la scoped por especificidad, pero conviene
  confirmar que no haya cruce inesperado fuera de `.landing-root`.
- **`ml-yellow` / `ml-yellow-dark`** y la clase `.btn-yellow` (en realidad
  verde): nombres legacy del esquema amarillo previo; siguen en los tokens pero
  el acento actual es verde. Evaluar renombrar para evitar confusión.
- **Dos paletas de acento verde** ligeramente distintas conviven: la de la app
  (`ml-green = #22C55E`, `ml-green-dim = #16A34A`) y la de la landing
  (`--accent` = `#16A34A` light / `#22C55E` dark). Es intencional (la landing
  usa un verde un poco más oscuro en light), pero queda anotado por si se quiere
  unificar.
