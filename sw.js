// ============================================
// TRADEVISION PRO - SERVICE WORKER
// Version: 2.0.0
// Production-grade caching strategy
// ============================================

const CACHE_NAME = 'tradevision-v2';
const API_CACHE_NAME = 'tradevision-api-v1';

// Assets to cache immediately on install
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/engine.js',
  '/manifest.json',
  '/favicon.ico'
];

// Dynamic assets that can be cached on demand
const DYNAMIC_ASSETS = [
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css',
  'https://unpkg.com/lightweight-charts@4.2.2/dist/lightweight-charts.standalone.production.js'
];

// ============================================
// INSTALL EVENT - Cache static assets
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
// ACTIVATE EVENT - Clean up old caches
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
// FETCH EVENT - Handle requests with strategies
// ============================================
self.addEventListener('fetch', event => {
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
          return response || fetch(event.request).then(fetchResponse => {
            // Cache the fetched response for future
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, fetchResponse.clone());
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
          // Cache successful API responses
          if (response.ok) {
            const responseClone = response.clone();
            caches.open(API_CACHE_NAME).then(cache => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // Return cached API response if network fails
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
              cache.put(event.request, networkResponse.clone());
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
  // STRATEGY 4: Network Only (WebSocket, real-time)
  // ============================================
  if (url.protocol === 'wss:' || url.protocol === 'ws:') {
    // Don't cache WebSocket connections
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
            // Fallback to offline page
            return caches.match('/offline.html');
          });
      })
  );
});

// ============================================
// MESSAGE EVENT - Handle client messages
// ============================================
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          return caches.delete(cacheName);
        })
      );
    }).then(() => {
      console.log('[SW] Cache cleared');
      if (event.ports && event.ports[0]) {
        event.ports[0].postMessage({ type: 'CACHE_CLEARED' });
      }
    });
  }
});

// ============================================
// PERIODIC SYNC - Update in background
// ============================================
self.addEventListener('periodicsync', event => {
  if (event.tag === 'update-assets') {
    event.waitUntil(
      caches.open(CACHE_NAME).then(cache => {
        return cache.addAll(STATIC_ASSETS);
      })
    );
  }
});

// ============================================
// BACKGROUND FETCH - For large data
// ============================================
self.addEventListener('backgroundfetch', event => {
  if (event.registration.id === 'chart-data-update') {
    event.waitUntil(
      caches.open(API_CACHE_NAME).then(cache => {
        return cache.addAll(event.registration.requests);
      })
    );
  }
});

// ============================================
// PUSH EVENT - Handle push notifications
// ============================================
self.addEventListener('push', event => {
  let data = {
    title: 'TradeVision Pro',
    body: 'You have a new alert!',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-96.png',
    tag: 'tradevision-alert',
    vibrate: [200, 100, 200]
  };
  
  if (event.data) {
    try {
      data = JSON.parse(event.data.text());
    } catch (e) {
      data.body = event.data.text();
    }
  }
  
  const options = {
    body: data.body,
    icon: data.icon || '/icons/icon-192.png',
    badge: data.badge || '/icons/icon-96.png',
    tag: data.tag || 'tradevision-alert',
    vibrate: data.vibrate || [200, 100, 200],
    data: data.data || {},
    actions: [
      {
        action: 'open',
        title: 'Open App',
        icon: '/icons/icon-96.png'
      },
      {
        action: 'dismiss',
        title: 'Dismiss',
        icon: '/icons/icon-96.png'
      }
    ],
    requireInteraction: true,
    silent: false,
    renotify: true
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title || 'TradeVision Pro', options)
  );
});

// ============================================
// NOTIFICATION CLICK EVENT
// ============================================
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  if (event.action === 'dismiss') {
    return;
  }
  
  // Open the app
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(clientList => {
        // Try to focus an existing window
        for (let client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            return client.focus();
          }
        }
        // Open new window
        return clients.openWindow('/');
      })
  );
});

// ============================================
// SYNC EVENT - Offline data sync
// ============================================
self.addEventListener('sync', event => {
  if (event.tag === 'sync-trades') {
    event.waitUntil(
      // Logic to sync pending trades
      fetch('/api/sync-trades', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
          console.log('[SW] Trades synced:', data);
        })
        .catch(err => {
          console.error('[SW] Sync failed:', err);
        })
    );
  }
});

// ============================================
// DEBUG - Log cache status
// ============================================
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'DEBUG_CACHE') {
    caches.keys().then(cacheNames => {
      const status = { caches: [] };
      const promises = cacheNames.map(cacheName => {
        return caches.open(cacheName).then(cache => {
          return cache.keys().then(requests => {
            status.caches.push({
              name: cacheName,
              count: requests.length
            });
          });
        });
      });
      
      Promise.all(promises).then(() => {
        if (event.ports && event.ports[0]) {
          event.ports[0].postMessage(status);
        }
      });
    });
  }
});

console.log('✅ Service Worker loaded successfully');
