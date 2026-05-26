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
    vibrate: [200, 100, 200],
    data: {
      url: '/',
      symbol: null,
      price: null,
      type: 'alert'
    }
  };
  
  // Parse incoming data if available
  if (event.data) {
    try {
      const parsedData = JSON.parse(event.data.text());
      data = { ...data, ...parsedData };
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
    data: data.data || {
      url: '/',
      symbol: null,
      price: null,
      type: 'alert'
    },
    actions: [
      {
        action: 'open',
        title: 'Open Chart',
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
    renotify: true,
    timestamp: Date.now()
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title || 'TradeVision Pro', options)
  );
});

// ============================================
// NOTIFICATION CLICK EVENT - Handle notification clicks
// ============================================
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  // Handle action buttons
  if (event.action === 'dismiss') {
    return;
  }
  
  // Get the URL from notification data
  const url = event.notification.data?.url || '/';
  const symbol = event.notification.data?.symbol || null;
  const price = event.notification.data?.price || null;
  
  // Open or focus the app
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(clientList => {
        // Try to focus an existing window
        for (let client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            // If we have symbol/price data, send it to the client
            if (symbol || price) {
              client.postMessage({
                type: 'notification-click',
                symbol: symbol,
                price: price
              });
            }
            return client.focus();
          }
        }
        // Open new window with URL
        return clients.openWindow(url);
      })
  );
});

// ============================================
// MESSAGE EVENT - Handle messages from client
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
// NOTIFICATION CLICK EVENT - Handle notification clicks
// ============================================
self.addEventListener('notificationclick', event => {
  console.log('[SW] Notification clicked:', event.notification.tag);
  
  // Close the notification
  event.notification.close();
  
  // Handle action buttons
  if (event.action === 'dismiss') {
    console.log('[SW] Notification dismissed');
    return;
  }
  
  // Get data from notification
  const notificationData = event.notification.data || {};
  const url = notificationData.url || '/';
  const symbol = notificationData.symbol || null;
  const price = notificationData.price || null;
  const type = notificationData.type || 'alert';
  
  console.log('[SW] Opening URL:', url);
  console.log('[SW] Data:', { symbol, price, type });
  
  // Open or focus the app
  event.waitUntil(
    clients.matchAll({ 
      type: 'window', 
      includeUncontrolled: true 
    })
    .then(clientList => {
      // Try to find an existing window
      for (let client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          console.log('[SW] Found existing client, focusing...');
          
          // Send data to the client
          if (symbol || price) {
            client.postMessage({
              type: 'notification-click',
              symbol: symbol,
              price: price,
              url: url,
              action: event.action || 'open'
            });
          }
          
          return client.focus();
        }
      }
      
      // No existing window, open new one
      console.log('[SW] No existing client, opening new window');
      return clients.openWindow(url);
    })
  );
});

// ============================================
// MESSAGE EVENT - Handle messages from clients
// ============================================
self.addEventListener('message', event => {
  console.log('[SW] Message received:', event.data);
  
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
  
  if (event.data && event.data.type === 'NOTIFICATION_CLICKED') {
    // Handle notification clicked from client
    console.log('[SW] Notification clicked from client:', event.data);
  }
});

// ============================================
// CLIENT MESSAGE HANDLER - For sending data to client
// ============================================
self.addEventListener('message', event => {
  // Handle client messages
  if (event.data && event.data.type === 'PING') {
    event.ports[0].postMessage({ type: 'PONG' });
  }
});

console.log('✅ Service Worker v2.1.0 loaded');
