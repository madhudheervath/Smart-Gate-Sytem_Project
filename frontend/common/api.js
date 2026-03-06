// Centralized API Client for Smart Gate System

const isPublicAuthEndpoint = (endpoint) => {
    if (!endpoint) return false;
    return endpoint === '/auth/login' || endpoint === '/auth/register';
};

const runtimeApi = (typeof CONFIG !== 'undefined' && typeof CONFIG.createApiClient === 'function')
    ? CONFIG.createApiClient()
    : {
        getBase: () => window.location.origin,
        async fetch(path, options = {}) {
            return fetch(`${window.location.origin}${path}`, options);
        }
    };

const handleSessionExpiry = () => {
    if (typeof NotificationManager !== 'undefined' && NotificationManager?.error) {
        NotificationManager.error('Session expired. Please login again.');
    }
    API.removeToken();
    setTimeout(() => {
        window.location.href = '/';
    }, 2000);
};

// API Client
const API = {
    baseURL: runtimeApi.getBase(),

    // Set authorization token
    setToken: (token) => {
        localStorage.setItem('token', token);
    },

    // Get authorization token
    getToken: () => {
        return localStorage.getItem('token');
    },

    // Remove token (logout)
    removeToken: () => {
        localStorage.removeItem('token');
    },

    fetchWithFallback: async (endpoint, options = {}) => {
        const response = await runtimeApi.fetch(endpoint, options);
        API.baseURL = runtimeApi.getBase();
        return response;
    },

    // Make authenticated request
    request: async (endpoint, options = {}) => {
        const token = API.getToken();
        const publicAuthEndpoint = isPublicAuthEndpoint(endpoint);

        // Check token expiry before making request for protected endpoints.
        if (token && typeof TokenManager !== 'undefined' && !publicAuthEndpoint) {
            if (TokenManager.isExpired(token)) {
                handleSessionExpiry();
                throw new Error('Token expired');
            }
        }

        const config = {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        // Add authorization header for all protected endpoints, including /auth/me.
        if (token && !publicAuthEndpoint) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await API.fetchWithFallback(endpoint, config);

            // Handle 401 Unauthorized for protected endpoints.
            if (response.status === 401 && !publicAuthEndpoint) {
                handleSessionExpiry();
                throw new Error('Unauthorized');
            }

            return response;
        } catch (error) {
            // Check if offline
            if (!navigator.onLine) {
                throw new Error('You are offline. Please check your internet connection.');
            }
            throw error;
        }
    },

    // GET request
    get: async (endpoint) => {
        return API.request(endpoint, { method: 'GET' });
    },

    // POST request
    post: async (endpoint, data) => {
        return API.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    // PUT request
    put: async (endpoint, data) => {
        return API.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    // DELETE request
    delete: async (endpoint) => {
        return API.request(endpoint, { method: 'DELETE' });
    },

    // POST with form data
    postForm: async (endpoint, formData) => {
        const token = API.getToken();

        const response = await API.fetchWithFallback(endpoint, {
            method: 'POST',
            headers: {
                'Authorization': token ? `Bearer ${token}` : undefined
            },
            body: formData
        });

        return response;
    },

    // POST with URL encoded data (for login)
    postUrlEncoded: async (endpoint, data) => {
        const formData = new URLSearchParams();
        for (const [key, value] of Object.entries(data)) {
            formData.append(key, value);
        }

        const response = await API.fetchWithFallback(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData
        });

        return response;
    }
};

// Specific API endpoints
const AuthAPI = {
    login: async (email, password) => {
        const response = await API.postUrlEncoded('/auth/login', {
            username: email,
            password: password
        });

        if (!response.ok) {
            let errorMsg = 'Invalid credentials';
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorData.message || errorMsg;
            } catch {
                errorMsg = response.status >= 500
                    ? `Server Error (${response.status})`
                    : errorMsg;
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();

        if (!data.access_token) {
            throw new Error('Invalid response: No access token received');
        }

        return data;
    },

    register: async (userData) => {
        const response = await API.post('/auth/register', userData);

        if (!response.ok) {
            let errorMsg = 'Registration failed';
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorMsg;
            } catch {
                errorMsg = await response.text() || errorMsg;
            }
            throw new Error(errorMsg);
        }

        return await response.json();
    },

    logout: () => {
        API.removeToken();
        window.location.href = '/';
    },

    getMe: async () => {
        const response = await API.get('/auth/me');

        if (!response.ok) {
            throw new Error('Failed to get user info');
        }

        const data = await response.json();

        if (!data) {
            throw new Error('Invalid response: No user data received');
        }

        return data;
    }
};

const PassAPI = {
    request: async (passType, reason, location = null) => {
        const payload = {
            pass_type: passType,
            reason: reason
        };
        if (location) {
            payload.latitude = location.latitude;
            payload.longitude = location.longitude;
        }

        const response = await API.post('/passes', payload);

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Failed to request pass');
        }

        return await response.json();
    },

    list: async () => {
        const response = await API.get('/passes');

        if (!response.ok) {
            throw new Error('Failed to load passes');
        }

        const data = await response.json();
        return Array.isArray(data) ? data : [];
    },

    dailyEntry: async (passType, location = null) => {
        const payload = { pass_type: passType };
        if (location) {
            payload.latitude = location.latitude;
            payload.longitude = location.longitude;
        }

        const response = await API.post('/passes/daily-entry', payload);

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Failed to create daily entry');
        }

        return await response.json();
    },

    emergencyExit: async (reason) => {
        const response = await API.post('/api/emergency_exit', { reason });

        if (!response.ok) {
            throw new Error('Emergency exit request failed');
        }

        return await response.json();
    }
};

const AdminAPI = {
    listPasses: async () => {
        const response = await API.get('/passes');

        if (!response.ok) {
            throw new Error('Failed to load passes');
        }

        const data = await response.json();
        return Array.isArray(data) ? data : [];
    },

    approvePass: async (passId) => {
        const response = await API.post(`/passes/${passId}/approve`, {});

        if (!response.ok) {
            throw new Error('Failed to approve pass');
        }

        return await response.json();
    },

    rejectPass: async (passId) => {
        const response = await API.post(`/passes/${passId}/reject`, {});

        if (!response.ok) {
            throw new Error('Failed to reject pass');
        }

        return await response.json();
    },

    getLogs: async () => {
        const response = await API.get('/scans');

        if (!response.ok) {
            throw new Error('Failed to load logs');
        }

        const data = await response.json();
        return Array.isArray(data) ? data : [];
    }
};

const FaceAPI = {
    register: async (imageFile) => {
        const formData = new FormData();
        formData.append('file', imageFile);

        const response = await API.postForm('/api/register_face', formData);

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Failed to register face');
        }

        return await response.json();
    },

    getStatus: async () => {
        const response = await API.get('/api/face_status');

        if (!response.ok) {
            throw new Error('Failed to get face status');
        }

        return await response.json();
    },

    verify: async (studentId, imageFile) => {
        const formData = new FormData();
        formData.append('student_id', studentId);
        formData.append('file', imageFile);

        const response = await API.postForm('/api/verify_face', formData);

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Verification failed');
        }

        return await response.json();
    }
};

const ParentAPI = {
    getAccessToken: async () => {
        const response = await API.get('/api/parent/access-token');

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Failed to create parent access link');
        }

        return await response.json();
    }
};

const NotificationAPI = {
    enable: async () => {
        const response = await API.post('/api/student/enable_notifications', {});

        if (!response.ok) {
            throw new Error('Failed to enable notifications');
        }

        return await response.json();
    },

    saveToken: async (fcmToken) => {
        const response = await API.post('/api/register_fcm_token', {
            fcm_token: fcmToken
        });

        if (!response.ok) {
            throw new Error('Failed to save FCM token');
        }

        return await response.json();
    },

    saveContact: async (studentPhone, parentName, parentPhone) => {
        const response = await API.post('/api/update_contact', {
            phone: studentPhone,
            parent_name: parentName,
            parent_phone: parentPhone
        });

        if (!response.ok) {
            throw new Error('Failed to save contact info');
        }

        return await response.json();
    }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        API,
        AuthAPI,
        PassAPI,
        AdminAPI,
        FaceAPI,
        NotificationAPI,
        ParentAPI
    };
}
