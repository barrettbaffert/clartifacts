/* clartifacts service worker — offline-first
   Bump VERSION whenever any page is updated so devices pick up changes. */
const VERSION = "clartifacts-v4";
const CORE = [
  "./",
  "index.html",
  "spelling.html",
  "space-finder-2v2.html",
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
        // Best-effort runtime caching (includes fonts); failures are fine.
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      });
    })
  );
});
