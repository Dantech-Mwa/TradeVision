// TradeVision Pro - Service Worker for Push Notifications
self.addEventListener('install', (event) => {
  console.log('📲 Service Worker installed');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('📲 Service Worker activated');
  event.waitUntil(clients.claim());
});

self.addEventListener('push', (event) => {
  if (event.data) {
    try {
      const data = event.data.json();
      const options = {
        body: data.body || 'New alert from TradeVision Pro',
        icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">📊</text></svg>',
        badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">📊</text></svg>',
        tag: 'tradevision-' + (data.tag || Date.now()),
        requireInteraction: true,
        vibrate: [200, 100, 200]
      };
      
      event.waitUntil(
        self.registration.showNotification(data.title || 'TradeVision Pro', options)
      );
    } catch(e) {
      event.waitUntil(
        self.registration.showNotification('TradeVision Pro', {
          body: event.data.text(),
          icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">📊</text></svg>'
        })
      );
    }
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow('/')
  );
});
