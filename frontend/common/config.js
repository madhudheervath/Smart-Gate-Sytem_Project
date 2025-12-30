// Configuration and Environment Settings
const CONFIG = {
    // API Base URL - Render Backend
    API_BASE: 'https://smart-gate-sytem-project.onrender.com',
    
    // Feature flags
    FEATURES: {
        OFFLINE_MODE: true,
        DARK_MODE: true,
        ANALYTICS: false,
        PWA: true
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
