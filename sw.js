/* clartifacts service worker — offline-first
   Bump VERSION whenever any page is updated so devices pick up changes. */
const VERSION = "clartifacts-v26";
const CORE = [
  "./",
  "index.html",
  "spelling.html",
  "space-finder-2v2.html",
  "space-finder-9v9.html",
  "wheel-trainer.html",
  "icon-shrimp.png",
  "icon-spell.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(VERSION).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then((hit) => {
      if (hit) return hit;
      return fetch(e.request).then((res) => {
        // Don't pin a 404 (e.g. a narration clip not rendered yet) until the
        // next VERSION bump. Cross-origin font files come back opaque with
        // ok === false even on success, so keep caching those.
        if (!res.ok && res.type !== "opaque") return res;
        // Best-effort runtime caching (includes fonts); failures are fine.
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      });
    })
  );
});
