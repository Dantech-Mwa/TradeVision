// ============================================
// TRADEVISION PRO - SERVICE WORKER
// Version: 2.1.0
// Complete with all event handlers
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
// FETCH EVENT
// ============================================
self.addEventListener('fetch', event => {
  if (event.request.method === 'HEAD') {
    event.respondWith(fetch(event.request));
    return;
  }
  
  const url = new URL(event.request.url);
  
  // Cache First for static assets
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
          if (response) return response;
          return fetch(event.request).then(fetchResponse => {
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
  
  // Network First for API calls
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
  
  // Default: fetch from network
  event.respondWith(fetch(event.request));
});

// ============================================
// PUSH EVENT
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
    data: data.data,
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
// NOTIFICATION CLICK EVENT
// ============================================
self.addEventListener('notificationclick', event => {
  console.log('[SW] Notification clicked:', event.notification.tag);
  
  event.notification.close();
  
  if (event.action === 'dismiss') {
    console.log('[SW] Notification dismissed');
    return;
  }
  
  const notificationData = event.notification.data || {};
  const url = notificationData.url || '/';
  const symbol = notificationData.symbol || null;
  const price = notificationData.price || null;
  const type = notificationData.type || 'alert';
  
  console.log('[SW] Opening URL:', url);
  console.log('[SW] Data:', { symbol, price, type });
  
  event.waitUntil(
    clients.matchAll({ 
      type: 'window', 
      includeUncontrolled: true 
    })
    .then(clientList => {
      for (let client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          console.log('[SW] Found existing client, focusing...');
          
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
      
      console.log('[SW] No existing client, opening new window');
      return clients.openWindow(url);
    })
  );
});

console.log('✅ Service Worker v2.1.0 loaded');
