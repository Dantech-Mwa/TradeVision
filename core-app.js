// core-app.js - Core framework to support the indicator and drawing engines
const AppCore = (function() {
    const state = {};
    const events = {};
    const modules = {};
    
    const core = {
        // Event system
        on: function(event, callback) {
            if (!events[event]) events[event] = [];
            events[event].push(callback);
        },
        
        emit: function(event, data) {
            console.log(`[AppCore] Emitting event: ${event}`, data);
            if (events[event]) {
                events[event].forEach(callback => {
                    try {
                        callback(data);
                    } catch (e) {
                        console.error(`Error in event handler for ${event}:`, e);
                    }
                });
            }
        },
        
        // State management
        setState: function(key, value) {
            if (typeof key === 'object') {
                Object.assign(state, key);
            } else {
                state[key] = value;
            }
            console.log(`[AppCore] State updated:`, state);
        },
        
        getState: function(key) {
            return key ? state[key] : state;
        },
        
        // Module system
        registerModule: async function(name, module) {
            console.log(`[AppCore] Registering module: ${name}`);
            modules[name] = module;
            if (module.init) {
                await module.init(this);
            }
            if (module.start) {
                await module.start(this);
            }
            return module;
        },
        
        // Utility functions
        log: function(...args) {
            console.log('[AppCore]', ...args);
        },
        
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },
        
        runTaskWithWorker: async function(task, payload) {
            console.log('[AppCore] Running task with worker:', task.name);
            return await task(payload);
        }
    };

    // Auto-initialize
    (async function() {
        console.log('[AppCore] Initializing...');
        // Set initial state
        core.setState({
            activeIndicators: new Set(),
            historyCache: {}
        });
    })();

    return core;
})();

// Make globally available
if (typeof window !== 'undefined') window.AppCore = AppCore;
