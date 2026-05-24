// Service worker minimo: solo permite que la app sea instalable como PWA.
// Network-first puro, sin pre-cache de assets (evita que un build viejo
// quede atrapado en cache y rompa la app despues de un deploy).
const CACHE_NAME = 'conciliacion-shell-v4';
const SHARE_CACHE = 'conciliacion-share-inbox';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // borrar TODOS los caches viejos (incluidos los de versiones anteriores
    // o los que dejo vite-plugin-pwa). Esto desbloquea PWAs instaladas
    // que quedaron con assets de un build que ya no existe.
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k !== CACHE_NAME && k !== SHARE_CACHE).map((k) => caches.delete(k))
    );
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

// Share Target: cuando el usuario comparte un archivo desde WhatsApp/Galeria
// hacia la PWA, el SO hace POST a /compartir. Guardamos los archivos en una
// cache temporal y redirigimos a GET /compartir para que la SPA los lea.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method === 'POST' && url.pathname === '/compartir') {
    event.respondWith((async () => {
      try {
        const formData = await event.request.formData();
        const files = formData.getAll('files');
        const title = formData.get('title') || '';
        const text  = formData.get('text')  || '';
        const cache = await caches.open(SHARE_CACHE);
        // limpiar inbox previo
        const keys = await cache.keys();
        await Promise.all(keys.map((k) => cache.delete(k)));
        // guardar archivos
        const meta = [];
        for (let i = 0; i < files.length; i++) {
          const f = files[i];
          if (!(f instanceof File) || f.size === 0) continue;
          const key = `/__share__/file-${i}`;
          const resp = new Response(f, {
            headers: {
              'Content-Type': f.type || 'application/octet-stream',
              'X-Share-Filename': encodeURIComponent(f.name || `archivo-${i}`),
            },
          });
          await cache.put(key, resp);
          meta.push({ key, name: f.name || `archivo-${i}`, type: f.type || '', size: f.size });
        }
        await cache.put('/__share__/meta', new Response(JSON.stringify({ files: meta, title, text, ts: Date.now() }), {
          headers: { 'Content-Type': 'application/json' },
        }));
      } catch (ex) {
        // si algo falla, igual redirigimos para que la pagina muestre el error
      }
      return Response.redirect('/compartir?source=share', 303);
    })());
    return;
  }

  if (event.request.method !== 'GET') return;

  // Nunca interceptar requests a la API (otro origen): pasan derecho
  if (url.origin !== self.location.origin) return;

  // Lectura de archivos compartidos: la pagina /compartir los pide aca
  if (url.pathname.startsWith('/__share__/')) {
    event.respondWith((async () => {
      const cache = await caches.open(SHARE_CACHE);
      const hit = await cache.match(url.pathname);
      return hit || new Response('', { status: 404 });
    })());
    return;
  }

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
