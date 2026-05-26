// ============================================
// TRADEVISION PRO - SERVICE WORKER
// Version: 2.1.0
// Fixed: HEAD requests, response cloning, error handling
// ============================================

const CACHE_NAME = 'tradevision-v2';
const API_CACHE_NAME = 'tradevision-api-v1';

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/engine.js',
  '/manifest.json',
  '/favicon.ico'
];

// ============================================
// INSTALL EVENT
// ============================================
self.addEventListener('install', event => {
  console.log('[SW] Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[SW] Caching static assets...');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('[SW] Install complete');
        return self.skipWaiting();
      })
      .catch(err => {
        console.error('[SW] Install error:', err);
      })
  );
});

// ============================================
// ACTIVATE EVENT
// ============================================
self.addEventListener('activate', event => {
  console.log('[SW] Activating...');
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME && cacheName !== API_CACHE_NAME) {
            console.log('[SW] Removing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      console.log('[SW] Activate complete');
      return self.clients.claim();
    })
  );
});

// ============================================
// FIXED FETCH EVENT
// ============================================
self.addEventListener('fetch', event => {
  // Skip HEAD requests
  if (event.request.method === 'HEAD') {
    event.respondWith(fetch(event.request));
    return;
  }
  
  const url = new URL(event.request.url);
  
  // ============================================
  // STRATEGY 1: Cache First (Static assets)
  // ============================================
  if (url.pathname.endsWith('.js') || 
      url.pathname.endsWith('.css') || 
      url.pathname.endsWith('.html') ||
      url.pathname.endsWith('.json') ||
      url.pathname.endsWith('.png') ||
      url.pathname.endsWith('.svg') ||
      url.pathname.endsWith('.ico')) {
    
    event.respondWith(
      caches.match(event.request)
        .then(response => {
          if (response) {
            return response;
          }
          
          return fetch(event.request).then(fetchResponse => {
            // Clone BEFORE consuming
            const responseClone = fetchResponse.clone();
            
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseClone);
            });
            
            return fetchResponse;
          });
        })
    );
    return;
  }
  
  // ============================================
  // STRATEGY 2: Network First (API calls)
  // ============================================
  if (url.pathname.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response.ok) {
            const responseClone = response.clone();
            caches.open(API_CACHE_NAME).then(cache => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          return caches.match(event.request);
        })
    );
    return;
  }
  
  // ============================================
  // STRATEGY 3: Stale While Revalidate (Chart data)
  // ============================================
  if (url.pathname.includes('/proxy') || 
      url.pathname.includes('/klines') ||
      url.pathname.includes('/ticker')) {
    
    event.respondWith(
      caches.open(API_CACHE_NAME).then(cache => {
        return cache.match(event.request).then(cachedResponse => {
          const fetchPromise = fetch(event.request)
            .then(networkResponse => {
              const responseClone = networkResponse.clone();
              cache.put(event.request, responseClone);
              return networkResponse;
            })
            .catch(() => {
              return new Response('Network error', { status: 503 });
            });
          
          return cachedResponse || fetchPromise;
        });
      })
    );
    return;
  }
  
  // ============================================
  // STRATEGY 4: Network Only (WebSocket)
  // ============================================
  if (url.protocol === 'wss:' || url.protocol === 'ws:') {
    event.respondWith(fetch(event.request));
    return;
  }
  
  // ============================================
  // STRATEGY 5: Fallback to network (default)
  // ============================================
  event.respondWith(
    fetch(event.request)
      .catch(() => {
        return caches.match(event.request)
          .then(cached => {
            if (cached) {
              return cached;
            }
            return caches.match('/offline.html');
          });
      })
  );
});

// ============================================
// PUSH EVENT (Keep existing)
// ============================================
self.addEventListener('push', event => {
  // Your existing push handler
});

// ============================================
// NOTIFICATION CLICK EVENT (Keep existing)
// ============================================
self.addEventListener('notificationclick', event => {
  // Your existing notification handler
});

console.log('✅ Service Worker v2.1.0 loaded');
