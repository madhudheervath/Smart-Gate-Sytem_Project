// Utility Functions for Smart Gate System

// ==================== LOGGER ====================
const logger = {
    debug: (message, data = null) => {
        if (window.location.hostname === 'localhost') {
            console.log(`[DEBUG] ${message}`, data || '');
        }
    },
    info: (message, data = null) => {
        if (window.location.hostname === 'localhost') {
            console.info(`[INFO] ${message}`, data || '');
        }
    },
    warn: (message, data = null) => {
        console.warn(`[WARN] ${message}`, data || '');
    },
    error: (message, error = null) => {
        console.error(`[ERROR] ${message}`, error || '');
        // In production, send to error tracking service
        if (window.errorTracker) {
            window.errorTracker.log({ message, error });
        }
    }
};

// ==================== LOADING STATES ====================
const LoadingManager = {
    show: (elementId, message = 'Loading...') => {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        element.innerHTML = `
            <div class="loading-container" style="
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 60px 20px;
                gap: 20px;
            ">
                <div class="loading-spinner" style="
                    width: 50px;
                    height: 50px;
                    border: 4px solid rgba(102, 126, 234, 0.2);
                    border-top: 4px solid #667eea;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                "></div>
                <p style="
                    color: #666;
                    font-size: 16px;
                    font-weight: 500;
                ">${message}</p>
            </div>
            <style>
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        `;
    },
    
    hide: (elementId) => {
        const element = document.getElementById(elementId);
        if (!element) return;
        // Element will be populated with actual content by calling function
    },
    
    showButton: (buttonId, text = 'Loading...') => {
        const button = document.getElementById(buttonId);
        if (!button) return;
        
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.innerHTML = `
            <span style="display: inline-flex; align-items: center; gap: 8px;">
                <span class="btn-spinner" style="
                    width: 16px;
                    height: 16px;
                    border: 2px solid rgba(255,255,255,0.3);
                    border-top: 2px solid white;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                "></span>
                ${text}
            </span>
        `;
    },
    
    hideButton: (buttonId) => {
        const button = document.getElementById(buttonId);
        if (!button) return;
        
        button.disabled = false;
        button.textContent = button.dataset.originalText || 'Submit';
    }
};

// ==================== NOTIFICATIONS ====================
const NotificationManager = {
    show: (type, message, duration = 5000) => {
        // Remove existing notifications
        const existing = document.querySelector('.toast-notification');
        if (existing) existing.remove();
        
        const colors = {
            success: { bg: '#28a745', icon: '✓' },
            error: { bg: '#dc3545', icon: '✕' },
            warning: { bg: '#ffc107', icon: '⚠' },
            info: { bg: '#17a2b8', icon: 'ℹ' }
        };
        
        const config = colors[type] || colors.info;
        
        const toast = document.createElement('div');
        toast.className = 'toast-notification';
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${config.bg};
            color: white;
            padding: 16px 24px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
            z-index: 10000;
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 600;
            animation: slideInRight 0.3s ease-out;
            max-width: 400px;
        `;
        
        toast.innerHTML = `
            <span style="font-size: 20px;">${config.icon}</span>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" style="
                background: none;
                border: none;
                color: white;
                font-size: 20px;
                cursor: pointer;
                padding: 0;
                margin-left: 8px;
            ">×</button>
            <style>
                @keyframes slideInRight {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            </style>
        `;
        
        document.body.appendChild(toast);
        
        if (duration > 0) {
            setTimeout(() => toast.remove(), duration);
        }
    },
    
    success: (message) => NotificationManager.show('success', message),
    error: (message) => NotificationManager.show('error', message),
    warning: (message) => NotificationManager.show('warning', message),
    info: (message) => NotificationManager.show('info', message)
};

// ==================== VALIDATION ====================
const Validator = {
    email: (email) => {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    },
    
    password: (password) => {
        return password && password.length >= 6;
    },
    
    phone: (phone) => {
        const regex = /^[\d\s\+\-\(\)]+$/;
        return regex.test(phone) && phone.replace(/\D/g, '').length >= 10;
    },
    
    required: (value) => {
        return value && value.toString().trim().length > 0;
    },
    
    minLength: (value, min) => {
        return value && value.length >= min;
    },
    
    maxLength: (value, max) => {
        return value && value.length <= max;
    }
};

// ==================== TOKEN MANAGEMENT ====================
const TokenManager = {
    isExpired: (token) => {
        if (!token) return true;
        
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.exp * 1000 < Date.now();
        } catch (e) {
            logger.error('Failed to parse token', e);
            return true;
        }
    },
    
    getTimeUntilExpiry: (token) => {
        if (!token) return 0;
        
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.exp * 1000 - Date.now();
        } catch (e) {
            return 0;
        }
    },
    
    shouldRefresh: (token) => {
        const timeLeft = TokenManager.getTimeUntilExpiry(token);
        return timeLeft > 0 && timeLeft < 300000; // Less than 5 minutes
    }
};

// ==================== API HELPER ====================
const APIHelper = {
    handleResponse: async (response) => {
        if (!response) {
            throw new Error('No response received from server');
        }
        
        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data) {
            throw new Error('Invalid response: No data received');
        }
        
        return data;
    },
    
    handleError: (error, context = 'Operation') => {
        logger.error(`${context} failed`, error);
        
        let message = 'An unexpected error occurred';
        
        if (error.message) {
            message = error.message;
        } else if (typeof error === 'string') {
            message = error;
        }
        
        // Check for network errors
        if (!navigator.onLine) {
            message = 'You are offline. Please check your internet connection.';
        } else if (error.message?.includes('Failed to fetch')) {
            message = 'Unable to connect to server. Please try again.';
        } else if (error.message?.includes('401') || error.message?.includes('Unauthorized')) {
            message = 'Session expired. Please login again.';
            // Auto logout
            setTimeout(() => {
                localStorage.removeItem('token');
                window.location.href = '/';
            }, 2000);
        }
        
        NotificationManager.error(message);
        return message;
    }
};

// ==================== DEBOUNCE ====================
function debounce(func, wait = 500) {
    let timeout;
    return function executedFunction(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// ==================== FORMAT HELPERS ====================
const Format = {
    date: (dateString) => {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },
    
    time: (dateString) => {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    datetime: (dateString) => {
        if (!dateString) return 'N/A';
        return `${Format.date(dateString)} ${Format.time(dateString)}`;
    },
    
    timeAgo: (dateString) => {
        if (!dateString) return 'N/A';
        
        const seconds = Math.floor((new Date() - new Date(dateString)) / 1000);
        
        let interval = seconds / 31536000;
        if (interval > 1) return Math.floor(interval) + " years ago";
        
        interval = seconds / 2592000;
        if (interval > 1) return Math.floor(interval) + " months ago";
        
        interval = seconds / 86400;
        if (interval > 1) return Math.floor(interval) + " days ago";
        
        interval = seconds / 3600;
        if (interval > 1) return Math.floor(interval) + " hours ago";
        
        interval = seconds / 60;
        if (interval > 1) return Math.floor(interval) + " minutes ago";
        
        return "just now";
    }
};

// ==================== OFFLINE DETECTION ====================
const OfflineManager = {
    init: () => {
        window.addEventListener('online', () => {
            NotificationManager.success('Connection restored');
            OfflineManager.onOnline();
        });
        
        window.addEventListener('offline', () => {
            NotificationManager.warning('You are offline. Some features may not work.');
        });
    },
    
    onOnline: () => {
        // Refresh data when back online
        if (typeof loadPasses === 'function') loadPasses();
        if (typeof loadUserInfo === 'function') loadUserInfo();
    },
    
    isOnline: () => navigator.onLine
};

// ==================== EXPORT ====================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        logger,
        LoadingManager,
        NotificationManager,
        Validator,
        TokenManager,
        APIHelper,
        debounce,
        Format,
        OfflineManager
    };
}
