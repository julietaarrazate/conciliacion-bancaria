// Service Worker mínimo para que la app sea instalable como PWA
// No hace cache agresivo - delega todo a la red para tener datos siempre frescos
const CACHE_NAME = 'conciliacion-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  // Network-first: intenta red, si falla cae a cache
  if (event.request.method !== 'GET') return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Cachear solo recursos estáticos del propio origen
        if (
          response.ok &&
          event.request.url.startsWith(self.location.origin) &&
          (event.request.url.includes('/assets/') ||
            event.request.url.endsWith('.js') ||
            event.request.url.endsWith('.css') ||
            event.request.url.endsWith('.svg') ||
            event.request.url.endsWith('.png') ||
            event.request.url.endsWith('/'))
        ) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((r) => r || new Response('offline', { status: 503 })))
  );
});
