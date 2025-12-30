// Centralized API Client for Smart Gate System

// Get API base URL from config
// Get API base URL from config
const getAPIBase = () => {
    if (typeof CONFIG !== 'undefined' && CONFIG.API_BASE) {
        return CONFIG.API_BASE;
    }
    return window.location.hostname === 'localhost'
        ? 'http://localhost:8080'
        : window.location.origin;
};

// API Client
const API = {
    baseURL: getAPIBase(),

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

    // Make authenticated request
    request: async (endpoint, options = {}) => {
        const token = API.getToken();

        // Check token expiry before making request
        if (token && typeof TokenManager !== 'undefined') {
            if (TokenManager.isExpired(token)) {
                NotificationManager.error('Session expired. Please login again.');
                API.removeToken();
                setTimeout(() => {
                    window.location.href = '/';
                }, 2000);
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

        // Add authorization header if token exists
        if (token && !endpoint.includes('/auth/login')) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(`${API.baseURL}${endpoint}`, config);

            // Handle 401 Unauthorized
            if (response.status === 401) {
                NotificationManager.error('Session expired. Please login again.');
                API.removeToken();
                setTimeout(() => {
                    window.location.href = '/';
                }, 2000);
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

        const response = await fetch(`${API.baseURL}${endpoint}`, {
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

        const response = await fetch(`${API.baseURL}${endpoint}`, {
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
            throw new Error('Invalid credentials');
        }

        const data = await response.json();

        if (!data.access_token) {
            throw new Error('Invalid response: No access token received');
        }

        API.setToken(data.access_token);
        return data;
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
    request: async (passType, reason) => {
        const response = await API.post('/api/student/request_pass', {
            pass_type: passType,
            reason: reason
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Failed to request pass');
        }

        return await response.json();
    },

    list: async () => {
        const response = await API.get('/api/student/my_passes');

        if (!response.ok) {
            throw new Error('Failed to load passes');
        }

        const data = await response.json();
        return Array.isArray(data) ? data : [];
    },

    dailyEntry: async (passType, location = null) => {
        const payload = { pass_type: passType };
        if (location) {
            payload.location = location;
        }

        const response = await API.post('/api/student/daily_entry', payload);

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
        const response = await API.get('/api/admin/passes');

        if (!response.ok) {
            throw new Error('Failed to load passes');
        }

        const data = await response.json();
        return Array.isArray(data) ? data : [];
    },

    approvePass: async (passId) => {
        const response = await API.post(`/api/admin/approve_pass/${passId}`, {});

        if (!response.ok) {
            throw new Error('Failed to approve pass');
        }

        return await response.json();
    },

    rejectPass: async (passId) => {
        const response = await API.post(`/api/admin/reject_pass/${passId}`, {});

        if (!response.ok) {
            throw new Error('Failed to reject pass');
        }

        return await response.json();
    },

    getLogs: async () => {
        const response = await API.get('/api/admin/logs');

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
        formData.append('face_image', imageFile);

        const response = await API.postForm('/api/student/register_face', formData);

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Failed to register face');
        }

        return await response.json();
    },

    getStatus: async () => {
        const response = await API.get('/api/student/face_status');

        if (!response.ok) {
            throw new Error('Failed to get face status');
        }

        return await response.json();
    },

    verify: async (studentId, imageFile) => {
        const formData = new FormData();
        formData.append('student_id', studentId);
        formData.append('face_image', imageFile);

        const response = await API.postForm('/api/guard/verify_face', formData);

        if (!response.ok) {
            const error = await response.text();
            throw new Error(error || 'Verification failed');
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
        const response = await API.post('/api/student/save_fcm_token', {
            fcm_token: fcmToken
        });

        if (!response.ok) {
            throw new Error('Failed to save FCM token');
        }

        return await response.json();
    },

    saveContact: async (studentPhone, parentName, parentPhone) => {
        const response = await API.post('/api/student/save_contact', {
            student_phone: studentPhone,
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
        NotificationAPI
    };
}
