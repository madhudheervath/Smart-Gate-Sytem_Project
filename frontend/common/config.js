function isLocalhostHost(hostname) {
    return hostname === 'localhost' || hostname === '127.0.0.1';
}

function getApiCandidates() {
    const host = window.location.hostname;
    if (!isLocalhostHost(host)) {
        return [
            'https://smart-gate-sytem-project.onrender.com',
            window.location.origin
        ].filter(Boolean).filter((value, index, array) => array.indexOf(value) === index);
    }

    const candidates = [];
    const path = window.location.pathname || '';
    if (path.startsWith('/frontend/')) {
        candidates.push(window.location.origin);
        candidates.push(`${window.location.protocol}//${host}:8000`);
        candidates.push(`${window.location.protocol}//${host}:8080`);
    } else {
        candidates.push(`${window.location.protocol}//${host}:8000`);
        candidates.push(`${window.location.protocol}//${host}:8080`);
        candidates.push(window.location.origin);
    }

    return candidates.filter(Boolean).filter((value, index, array) => array.indexOf(value) === index);
}

function resolveLocalApiBase() {
    return getApiCandidates()[0] || window.location.origin;
}

function createApiClient() {
    let activeBase = resolveLocalApiBase();

    return {
        getBase() {
            return activeBase;
        },

        getWsBase() {
            return activeBase.replace(/^http/, 'ws');
        },

        async fetch(path, options = {}) {
            const candidates = [activeBase, ...getApiCandidates()].filter(Boolean);
            let lastResponse = null;
            let lastError = null;
            const isLocalhost = isLocalhostHost(window.location.hostname);

            for (const base of [...new Set(candidates)]) {
                try {
                    const response = await fetch(`${base}${path}`, options);
                    if (isLocalhost && (response.status === 404 || response.status === 405 || response.status === 501)) {
                        lastResponse = response;
                        continue;
                    }

                    activeBase = base;
                    return response;
                } catch (error) {
                    lastError = error;
                }
            }

            if (lastResponse) {
                return lastResponse;
            }

            throw lastError || new Error('API request failed');
        }
    };
}

// Configuration and Environment Settings
const CONFIG = {
    // API Base URL - support both FastAPI-served frontend and plain static localhost frontend
    API_BASE: resolveLocalApiBase(),
    getApiCandidates,
    createApiClient,

    // Feature flags
    FEATURES: {
        OFFLINE_MODE: true,
        DARK_MODE: true,
        ANALYTICS: false,
        PWA: true,
        SELF_REGISTRATION: false,
        ACCOUNT_REQUESTS: true,
        REAL_PUSH_NOTIFICATIONS: false
    },

    // Timeouts
    TIMEOUTS: {
        API_REQUEST: 30000,  // 30 seconds
        SESSION_WARNING: 300000,  // 5 minutes
        SESSION_TIMEOUT: 3600000  // 1 hour
    },

    // Pagination
    PAGINATION: {
        DEFAULT_PAGE_SIZE: 10,
        MAX_PAGE_SIZE: 100
    },

    // GPS Settings
    GPS: {
        ENABLE_GEOFENCING: true,
        CAMPUS_CENTER: {
            latitude: 31.7767,
            longitude: 76.9865
        },
        CAMPUS_RADIUS: 5000  // 5km in meters
    },

    // Notification Settings
    NOTIFICATION: {
        DURATION: 5000,  // 5 seconds
        AUTO_DISMISS: true
    }
};

// Export configuration
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CONFIG;
}
