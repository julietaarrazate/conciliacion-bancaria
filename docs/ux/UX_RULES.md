# Reglas de UX — Cuadra (frontend React + PWA)

Convenciones transversales de experiencia de usuario del frontend. Todo lo
documentado acá está basado en código real; las rutas se citan relativas a la
raíz del repo.

Documentos relacionados:
- Sistema de diseño (tokens, paleta, componentes): [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)
- Reglas de negocio (qué significan los estados, flujo de conciliación): [../business](../business)
- Bugs recurrentes (fechas, montos, share): [../../BUGS.md](../../BUGS.md)

---

## 1. Tema claro / oscuro persistido

Store: `frontend/src/store/theme.ts` (Zustand).

- Dos temas: `'light'` | `'dark'`. Dark mode es el modo "Linear" de marca
  (fondo `#0B0B0F`, acento verde) — ver [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md).
- **Persistencia**: el tema elegido se guarda en `localStorage` bajo la clave
  `app-theme`. Si no hay valor guardado, se respeta la preferencia del sistema
  vía `window.matchMedia('(prefers-color-scheme: dark)')`.
- **Aplicación al DOM**: el tema se materializa agregando/quitando la clase
  `dark` en `document.documentElement` (`darkMode: 'class'` en
  `frontend/tailwind.config.js`). `toggle()` actualiza store + localStorage +
  clase del `<html>`; `applyToDocument()` solo re-sincroniza la clase.
- **Arranque**: `App.tsx` llama `applyToDocument()` en un `useEffect` inicial,
  para que el primer render ya tenga el tema correcto.
- **Disparadores en UI**: hay toggle de tema en el sidebar
  (`frontend/src/components/Layout.tsx`, botón "Modo oscuro/Modo claro") y en el
  header mobile (ícono sol/luna).

Regla: cualquier color que dependa del tema se escribe con variantes
`dark:` de Tailwind, nunca con condicionales de JS sobre el valor del store.

---

## 2. PWA instalable + Service Worker

Manifest: `frontend/public/manifest.webmanifest` · SW: `frontend/public/sw.js`.

### Manifest
- `display: standalone`, `orientation: portrait`, `start_url: "/"`, `scope: "/"`.
- `theme_color` y `background_color` = `#0B0B0F` (coherente con dark mode).
- `lang: "es-AR"`, categorías `finance / business / productivity`.
- Íconos SVG + PNG en 192/512 (`purpose: any maskable`).

### Service worker — network-first puro (sin pre-cache)
Diseño deliberado para que un build viejo no quede atrapado en cache y rompa la
app después de un deploy:
- En `install` → `skipWaiting()`; en `activate` → borra **todos** los caches que
  no sean el shell actual (`conciliacion-shell-v4`) ni el inbox de compartir, y
  hace `clients.claim()`.
- **Navegación** (`mode === 'navigate'`): siempre va a la red; solo cae a cache
  (`/`) si el dispositivo está totalmente offline (devuelve `503 offline`).
- **Assets estáticos** (JS/CSS con hash): network-first con fallback a cache.
- **Nunca** intercepta requests a la API (otro origen) — pasan derecho.
- Mensajes soportados: `SKIP_WAITING` y `SELF_DESTROY` (desregistra el SW y
  recarga los clients — útil para limpiar instalaciones corruptas).

### Share Target (recibir archivos desde WhatsApp / Galería)
- El manifest declara `share_target` → `POST /compartir` (multipart),
  aceptando imágenes, PDF, jpg/png/webp/heic.
- El SW intercepta ese POST, guarda los archivos en una cache temporal
  (`conciliacion-share-inbox`, limpiando el inbox previo) bajo claves
  `/__share__/file-N` más un `/__share__/meta` JSON, y redirige (303) a
  `GET /compartir?source=share`.
- La página `frontend/src/pages/Compartir.tsx` lee esos archivos pidiéndolos al
  SW (`/__share__/...`) y los enruta al flujo correspondiente.
- Compartir por WhatsApp es un **área de bugs recurrentes** — antes de tocarla,
  leer [../../BUGS.md](../../BUGS.md).

### Web Push (VAPID)
- El SW maneja `push` mostrando notificación nativa (`title`, `body`, ícono
  `/icon-192.svg`, `tag: 'cuadra-alert'`, `renotify`).
- En `notificationclick`: enfoca una ventana existente del origen y navega a
  `data.url`, o abre una nueva.
- Suscripción y setup desde `/perfil` (requiere PWA instalada en Android Chrome).
  Backend dispara push de alertas a las 10:00 ART (ver `CLAUDE.md` → Schedulers).

---

## 3. Mobile-first + drawer

Layout: `frontend/src/components/Layout.tsx`.

- **Desktop** (`md:`): sidebar fijo de 224px (`w-56`) con la navegación completa
  filtrada por permisos.
- **Mobile**: header superior de 48px (logo + buscar + campana de alertas +
  toggle tema) y **bottom navigation** de 4 ítems (Resumen, Conciliar, Clientes,
  Historial) + botón "Más" que abre el **drawer** lateral con la nav completa.
- **Gestos del drawer**:
  - Swipe desde el borde izquierdo (primeros 25px) hacia la derecha → abre.
  - Swipe a la izquierda dentro del drawer → cierra.
  - Tap en el overlay → cierra.
- **Safe area iOS**: la bottom nav usa `env(safe-area-inset-bottom)` (clases
  `.bottom-nav-bar` y `.pb-safe-nav` en `frontend/src/styles/index.css`).
- La navegación se filtra por permiso/superadmin (`hasPermission`) antes de
  renderizar — los ítems sin acceso ni se muestran. La protección real de cada
  ruta vive en `App.tsx` (`ProtectedRoute`), no solo en el menú.

---

## 4. Bloqueo de la app con PIN + biometría

Store: `frontend/src/store/lock.ts` · Guard: `frontend/src/components/AppLockGuard.tsx`
· Pantalla: `frontend/src/components/LockScreen.tsx`.

- **PIN**: nunca se guarda en claro. Se hashea con `SHA-256` y sal de dominio
  (`'cuadra-pin-v1:' + pin`) vía `crypto.subtle`. El store persiste solo el hash
  (`zustand/persist`, clave `cuadra-lock`).
- **Biometría (WebAuthn)**: opt-in tras tener PIN. Usa
  `navigator.credentials.create/get` con autenticador de plataforma
  (`platform`, `userVerification: 'required'`). Solo se persiste el
  `credentialId`. Quitar el PIN desactiva también la biometría.
- **Cuándo se bloquea** (`AppLockGuard`, solo si hay PIN + sesión activa):
  1. Al cargar la app (nuevo tab, refresh, link externo) — y `isLocked` se
     persiste, así que recargar con PIN activo deja la app bloqueada.
  2. Al pasar a background / minimizar (`visibilitychange` + `document.hidden`),
     con debounce de 1500ms para evitar falsos positivos durante animaciones de
     navegación SPA en mobile.
  3. Por inactividad: 5 minutos sin `mousemove/keydown/touchstart/scroll`.

### `suppressLock` — la excepción de descargas/cámara/compartir
Una descarga deliberada (abrir diálogo de guardar PDF/Excel) o abrir la cámara
dispara `visibilitychange`, pero el usuario **no** salió de la app. Para que eso
no bloquee la pantalla:
- `suppressLock(ms?)` setea `suppressUntil = now + ms` (default 8000ms). El guard
  ignora el bloqueo por background mientras `suppressUntil > now`.
- Helpers por caso de uso:
  - Descargas (api.ts): `_suppressLockForDownload()` → 8s, en todos los
    endpoints que devuelven blobs (`frontend/src/services/api.ts`).
  - Compartir: `suppressLockForShare()` → **20s** (el share sheet del SO tarda
    más) — `frontend/src/pages/Pagos.tsx`,
    `frontend/src/components/cheques/shared.tsx`.
  - Cámara/foto: `suppressLockForCamera()` → 8s, antes de abrir el `<input
    type=file capture>` (ver botón de foto en `Pagos.tsx` y `ModalCheque.tsx`).

Regla: **cualquier acción que ceda el foco al SO de forma intencional**
(descarga, share, cámara, selector de archivos) debe llamar a `suppressLock`
antes, o la app se bloqueará al volver el foco.

---

## 5. Toasts (notificaciones efímeras)

Store: `frontend/src/store/toast.ts` · UI: `frontend/src/components/Toaster.tsx`.

- 4 tipos: `success | error | info | warn`.
- Duración por defecto: 5000ms para `error`, 3500ms para el resto;
  configurable por llamada. Auto-dismiss por `setTimeout`.
- API utilitaria fuera de componentes: `toast.success(msg)`,
  `toast.error(msg)`, `toast.info(msg)`, `toast.warn(msg)`.
- Animación de entrada: `.toast-enter` (`frontend/src/styles/index.css`).

Regla: usar toasts para feedback no bloqueante (guardado OK, error de red). Para
decisiones del usuario, usar el modal de confirmación (sección 6).

---

## 6. Modales de confirmación

Store: `frontend/src/store/confirm.ts` · UI: `ConfirmDialog.tsx` + `ConfirmModal.tsx`.

- Patrón **promesa**: `confirmDialog({ title, message?, confirmLabel?,
  cancelLabel?, danger? })` devuelve `Promise<boolean>` que resuelve al elegir.
- `danger: true` para acciones destructivas (estilo rojo). Ejemplo real: cerrar
  sesión en `Layout.tsx`.
- Se monta una sola instancia (`<ConfirmDialog />`) en el `Layout`; cualquier
  parte de la app lo invoca por el store, sin pasar props.

Regla: **toda acción destructiva o irreversible** (borrar, cerrar sesión,
sobrescribir) pasa por `confirmDialog`, nunca por `window.confirm`.

---

## 7. Fechas locales sin bug de timezone

Utilidades: `frontend/src/utils/fecha.ts`.

`new Date().toISOString().slice(0,10)` devuelve la fecha en **UTC**. En
Argentina (UTC-3), entre medianoche y las 3 AM eso da la fecha de **ayer**, lo
que registraba pagos/cheques/arqueos un día antes en el Libro Diario.

Regla: para defaults de fecha y "hoy" usar siempre los helpers locales:
- `localIsoDate(d?)` → `YYYY-MM-DD` en hora local (sin desfase).
- `hoyIso()` → alias semántico de `localIsoDate()` para "hoy".
- `isoHaceNDias(n)` → fecha local de hace N días.

Nunca usar `toISOString().slice(0,10)` para fechas de negocio. Este es el bug
más recurrente del proyecto — detalle y casos en
[../../BUGS.md](../../BUGS.md) → "Fechas en zona horaria Argentina (UTC-3)".

---

## 8. Cold start de Render + retry

`frontend/src/services/api.ts` (interceptor axios) · `frontend/src/App.tsx`.

El backend corre en Render free tier (cold start ~30s; Neon también puede
dormir). El frontend lo absorbe sin romper la sesión:

- **Keep-alive**: `App.tsx` hace `GET /health` cada 14 minutos para que Render
  no duerma (complementa al ping externo de UptimeRobot cada 5 min).
- **Retry automático** (`_shouldRetry`, hasta `_MAX_RETRIES = 3`):
  - `502/503/504` → reintenta **cualquier** método (el handler no llegó a
    correr, es seguro).
  - Sin respuesta (error de red/timeout, `ERR_NETWORK`/`ECONNABORTED`) →
    reintenta **solo GET**, para no duplicar escrituras (POST/PUT/DELETE) que sí
    pudieron llegar al servidor.
- **No desloguear por cold start**: al rehidratar usuario en `App.tsx`, solo se
  cierra sesión ante un `401` real. Cualquier otro error (servidor despertando)
  conserva el token y reintenta; nunca saca al usuario por un cold start.

---

## 9. Paginación de tablas grandes

Patrón en `frontend/src/components/PlanillaPanel.tsx` (planillas conciliadas, el
caso de mayor volumen):

- `PAGE_SIZE = 100`. Estado `page` (base 0); la query pide
  `{ limit: PAGE_SIZE, offset: page * PAGE_SIZE }` al backend (no se traen todas
  las filas al cliente).
- `totalPages = Math.ceil(total_filtered / PAGE_SIZE)`.
- Cualquier cambio de filtro resetea `page` a 0.
- Controles: contador "Página X / Y · N filas (filtrado)" + botones
  anterior/siguiente (deshabilitados en los extremos). La numeración de fila
  mostrada considera el offset (`page * PAGE_SIZE + i + 1`).
- Filas compactas estilo Excel Macro vía `.row-15` (15px) en
  `frontend/src/styles/index.css`.

Regla: tablas potencialmente grandes paginan en servidor (limit/offset), no en
cliente; el filtro siempre vuelve a la página 1.

---

## 10. Otras convenciones

- **Búsqueda global ⌘K / Ctrl+K**: atajo global en `Layout.tsx` abre
  `SearchModal` (debounce 300ms, mínimo 2 caracteres) — busca clientes,
  planillas, movimientos y cheques.
- **Rutas lazy**: cada página se carga al navegar (`React.lazy` en `App.tsx`),
  con `PageFallback` de "cargando..."; Login y reset de password quedan eager
  para primer paint instantáneo.
- **Transición de página**: `.page-enter` (fade-up 180ms) al cambiar de ruta.
- **Selección de texto restringida en mobile**: el `body` desactiva selección y
  callout (`user-select: none`); se reactiva selectivamente en `input/textarea/
  td/.monto/code/pre/.selectable` (`frontend/src/styles/index.css`).
- **Alertas en la campana**: el `Layout` consulta `getAlertas()` cada 5 min y
  muestra un badge con el conteo.

---

## Pendiente de revisar

- El SW (`sw.js`) usa íconos `/icon-192.svg`; el manifest declara además
  variantes PNG. Verificar que ambos archivos existan en `frontend/public/`
  (no se confirmó en esta documentación).
- El `App.tsx` ante un error transitorio al rehidratar usuario reintenta
  `getCurrentUser()` **una sola vez** de forma manual (además del retry del
  interceptor); confirmar que ese doble reintento es intencional y no se
  solapa de forma redundante con `_shouldRetry`.
