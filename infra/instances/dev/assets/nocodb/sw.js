// irl.coop — neutralized NocoDB PWA service worker.
//
// The stock workbox SW's NavigationRoute (createHandlerBoundToURL("/")) can
// serve a stale/corrupted cached response — a bare "ok" — for the root path,
// permanently hijacking the app (the app never loads, so the SW never gets a
// chance to update itself). This no-op SW replaces it:
//
//   - on activation it clears EVERY cache (removing any cached "ok"), and
//   - it declares NO fetch listener, so the browser never routes requests
//     through a service worker again — NocoDB runs fully online.
//
// Mounted over the image's nc-gui/sw.js via the nocodb app spec's dev.volumes,
// so the fix survives regeneration and requires no NocoDB rebuild.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      try {
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
      } catch (_) {
        /* nothing cached */
      }
    })()
  );
});
