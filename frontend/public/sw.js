// Service worker minimo: solo permite que la app sea instalable como PWA.
// Network-first puro, sin pre-cache de assets (evita que un build viejo
// quede atrapado en cache y rompa la app despues de un deploy).
const CACHE_NAME = 'conciliacion-shell-v3';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // borrar TODOS los caches viejos (incluidos los de versiones anteriores
    // o los que dejo vite-plugin-pwa). Esto desbloquea PWAs instaladas
    // que quedaron con assets de un build que ya no existe.
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
  if (event.data === 'SELF_DESTROY') {
    self.registration.unregister().then(() => {
      self.clients.matchAll().then((clients) => clients.forEach((c) => c.navigate(c.url)));
    });
  }
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);

  // Nunca interceptar requests a la API (otro origen): pasan derecho
  if (url.origin !== self.location.origin) return;

  // index.html / navegacion: SIEMPRE red, fallback cache solo si esta totalmente offline
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((resp) => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put('/', clone));
          return resp;
        })
        .catch(() => caches.match('/').then((r) => r || new Response('offline', { status: 503 })))
    );
    return;
  }

  // Assets estaticos (JS/CSS con hash en el nombre): network-first con fallback a cache
  event.respondWith(
    fetch(event.request)
      .then((resp) => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return resp;
      })
      .catch(() => caches.match(event.request).then((r) => r || new Response('', { status: 503 })))
  );
});
