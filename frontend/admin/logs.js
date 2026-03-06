/**
 * Real-Time Entry/Exit Logs Dashboard
 * WebSocket + Chart.js + Live Updates
 */

let authToken = localStorage.getItem('adminToken');
let currentUser = null;
let dailyChart = null;
let hourlyChart = null;
let ws = null;
let allLogs = [];
let wsPingInterval = null;
const apiClient = CONFIG.createApiClient();
let chartRefreshTimeout = null;

async function apiFetch(path, options = {}) {
    return apiClient.fetch(path, options);
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function badgeClassForResult(result) {
    const normalized = String(result || '').toLowerCase();
    if (normalized === 'success') return 'success';
    if (normalized === 'expired' || normalized === 'invalid') return normalized;
    if (normalized === 'not-approved' || normalized === 'replay' || normalized === 'error') return 'warning';
    if (normalized === 'used') return 'info';
    return 'neutral';
}

function getResultLabel(result) {
    return String(result || '').replaceAll('-', ' ').toUpperCase();
}

function normalizeLog(log) {
    return {
        ...log,
        student_id: log.student_id || 'Unknown',
        student_name: log.student_name || 'Unknown',
        scan_type: log.scan_type || 'entry',
        result: log.result || 'unknown',
        gate: log.gate || (log.emergency ? 'Emergency Exit' : 'Main Gate'),
        details: log.details || '',
        time: log.time || '',
        date: log.date || '',
        timestamp: log.timestamp || '',
        emergency: Boolean(log.emergency),
    };
}

async function ensureAdminSession() {
    const token = localStorage.getItem('adminToken');
    if (!token) {
        window.location.href = 'index.html';
        return false;
    }

    const response = await apiFetch('/auth/me', {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    if (!response.ok) {
        localStorage.removeItem('adminToken');
        window.location.href = 'index.html';
        return false;
    }

    const user = await response.json();
    if (user.role !== 'admin') {
        localStorage.removeItem('adminToken');
        window.location.href = 'index.html';
        return false;
    }

    currentUser = user;
    return true;
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async function () {
    console.log('📊 Initializing Real-Time Logs Dashboard...');

    // Always try to get the latest token
    authToken = localStorage.getItem('adminToken');
    console.log('Token check:', authToken ? 'Found (length: ' + authToken.length + ')' : 'Not found');

    // Load dashboard components regardless
    // Backend will handle authentication
    console.log('Loading dashboard components...');

    try {
        const hasAdminSession = await ensureAdminSession();
        if (!hasAdminSession) {
            return;
        }

        await loadStatistics();
        await loadDailyChart();
        await loadHourlyChart();
        await loadRecentLogs();
        connectWebSocket();

        // Auto-refresh statistics every 30 seconds
        setInterval(loadStatistics, 30000);

        console.log('✅ All components initialized');
    } catch (error) {
        console.error('❌ Error initializing dashboard:', error);
    }
});

// ============================================================================
// STATISTICS
// ============================================================================

async function loadStatistics() {
    try {
        // Always get fresh token
        const token = localStorage.getItem('adminToken');
        const response = await apiFetch('/api/logs/statistics?days=7', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            console.error('Failed to load statistics:', response.status, response.statusText);
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const stats = await response.json();

        document.getElementById('studentsInCampus').textContent = stats.students_in_campus;
        document.getElementById('totalScans').textContent = stats.total_scans;
        document.getElementById('successRate').textContent = `${stats.success_rate}% success rate`;
        document.getElementById('entriesToday').textContent = stats.entries_today ?? stats.entries;
        document.getElementById('exitsToday').textContent = stats.exits_today ?? stats.exits;

        console.log('✅ Statistics loaded:', stats);
    } catch (error) {
        console.error('❌ Error loading statistics:', error);
        // Show zeros instead of error
        document.getElementById('studentsInCampus').textContent = '0';
        document.getElementById('totalScans').textContent = '0';
        document.getElementById('successRate').textContent = '0% success rate';
        document.getElementById('entriesToday').textContent = '0';
        document.getElementById('exitsToday').textContent = '0';
    }
}

// ============================================================================
// CHARTS
// ============================================================================

async function loadDailyChart() {
    try {
        const token = localStorage.getItem('adminToken');
        const response = await apiFetch('/api/logs/daily?days=7', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load daily stats');

        const data = await response.json();

        const ctx = document.getElementById('dailyChart').getContext('2d');

        if (dailyChart) {
            dailyChart.destroy();
        }

        dailyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'Entries',
                        data: data.entries,
                        backgroundColor: 'rgba(16, 185, 129, 0.5)',
                        borderColor: 'rgba(16, 185, 129, 1)',
                        borderWidth: 2
                    },
                    {
                        label: 'Exits',
                        data: data.exits,
                        backgroundColor: 'rgba(239, 68, 68, 0.5)',
                        borderColor: 'rgba(239, 68, 68, 1)',
                        borderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                }
            }
        });

        console.log('✅ Daily chart loaded');
    } catch (error) {
        console.error('❌ Error loading daily chart:', error);
    }
}

async function loadHourlyChart() {
    try {
        const token = localStorage.getItem('adminToken');
        const response = await apiFetch('/api/logs/hourly', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load hourly stats');

        const data = await response.json();

        const ctx = document.getElementById('hourlyChart').getContext('2d');

        if (hourlyChart) {
            hourlyChart.destroy();
        }

        hourlyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'Entries',
                        data: data.entries,
                        borderColor: 'rgba(16, 185, 129, 1)',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Exits',
                        data: data.exits,
                        borderColor: 'rgba(239, 68, 68, 1)',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        fill: true,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                }
            }
        });

        console.log('✅ Hourly chart loaded');
    } catch (error) {
        console.error('❌ Error loading hourly chart:', error);
    }
}

// ============================================================================
// LOGS TABLE
// ============================================================================

async function loadRecentLogs() {
    try {
        const token = localStorage.getItem('adminToken');
        const response = await apiFetch('/api/logs/recent?limit=100', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Failed to load logs');

        const data = await response.json();
        allLogs = (data.logs || []).map(normalizeLog);

        renderLogs(allLogs);

        console.log(`✅ Loaded ${allLogs.length} logs`);
    } catch (error) {
        console.error('❌ Error loading logs:', error);
        showEmptyState('Failed to load logs');
    }
}

function renderLogs(logs) {
    const tbody = document.getElementById('logsTableBody');

    if (!logs || logs.length === 0) {
        showEmptyState('No logs found');
        return;
    }

    tbody.innerHTML = logs.map((rawLog) => {
        const log = normalizeLog(rawLog);
        return `
        <tr ${log.emergency ? 'style="background: #fff5f5; border-left: 4px solid #dc3545;"' : ''}>
            <td>
                <div style="font-weight: 600;">${escapeHtml(log.time)}</div>
                <div style="font-size: 12px; color: #6b7280;">${escapeHtml(log.date)}</div>
                ${log.emergency ? '<div style="font-size: 11px; color: #dc3545; font-weight: 700; margin-top: 4px;">🚨 EMERGENCY</div>' : ''}
            </td>
            <td><strong>${escapeHtml(log.student_id)}</strong></td>
            <td>${escapeHtml(log.student_name)}</td>
            <td>
                <span class="badge ${log.scan_type}" ${log.emergency ? 'style="background: #dc3545; color: white;"' : ''}>
                    ${log.emergency ? '🚨 ' : ''}${log.scan_type === 'entry' ? '🟢 Entry' : '🔴 Exit'}
                </span>
            </td>
            <td>
                <span class="badge ${badgeClassForResult(log.result)}">
                    ${escapeHtml(getResultLabel(log.result))}
                </span>
            </td>
            <td>${escapeHtml(log.gate)}</td>
            <td style="font-size: 12px; color: #6b7280;">
                ${escapeHtml(log.details || '-')}
            </td>
        </tr>
    `;
    }).join('');
}

function showEmptyState(message) {
    const tbody = document.getElementById('logsTableBody');
    tbody.innerHTML = `
        <tr>
            <td colspan="7" class="empty-state">
                <div class="empty-state-icon">📭</div>
                <div>${message}</div>
            </td>
        </tr>
    `;
}

// ============================================================================
// WEBSOCKET - REAL-TIME UPDATES
// ============================================================================

function connectWebSocket() {
    try {
        const token = localStorage.getItem('adminToken');
        if (!token) {
            throw new Error('Missing admin token');
        }

        ws = new WebSocket(`${apiClient.getWsBase()}/ws/logs?token=${encodeURIComponent(token)}`);

        ws.onopen = () => {
            console.log('✅ WebSocket connected - Real-time updates active');
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);

                if (message.type === 'initial') {
                    console.log('📦 Received initial data');
                    allLogs = Array.isArray(message.data) ? message.data.map(normalizeLog) : [];
                    renderLogs(allLogs);
                } else if (message.type === 'new_scan') {
                    console.log('🔔 New scan received:', message.data);
                    handleNewScan(message.data);
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        ws.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
        };

        ws.onclose = () => {
            console.log('⚠️  WebSocket disconnected. Reconnecting in 5s...');
            setTimeout(connectWebSocket, 5000);
        };

        if (wsPingInterval) {
            clearInterval(wsPingInterval);
        }

        // Send ping every 30 seconds to keep connection alive
        wsPingInterval = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 30000);

    } catch (error) {
        console.error('❌ Error connecting WebSocket:', error);
    }
}

function handleNewScan(scanData) {
    // Add to beginning of logs array
    allLogs.unshift(normalizeLog(scanData));

    // Keep only last 100 logs in memory
    if (allLogs.length > 100) {
        allLogs.pop();
    }

    // Re-render table
    renderLogs(allLogs);

    // Update statistics
    loadStatistics();
    refreshChartsSoon();

    // Show notification (optional)
    showNotification(scanData);
}

function showNotification(scanData) {
    // You can add a toast notification here if desired
    console.log(`🔔 ${scanData.student_name} ${scanData.scan_type === 'entry' ? 'entered' : 'exited'} campus`);
}

function refreshChartsSoon() {
    if (chartRefreshTimeout) {
        clearTimeout(chartRefreshTimeout);
    }

    chartRefreshTimeout = setTimeout(() => {
        loadDailyChart();
        loadHourlyChart();
    }, 400);
}

// ============================================================================
// FILTERS & SEARCH
// ============================================================================

async function applyFilters() {
    const studentId = document.getElementById('searchStudent').value.trim();
    const scanType = document.getElementById('filterType').value;
    const result = document.getElementById('filterResult').value;
    const dateFrom = document.getElementById('filterDateFrom').value;
    const dateTo = document.getElementById('filterDateTo').value;

    try {
        const token = localStorage.getItem('adminToken');
        const params = new URLSearchParams();
        if (studentId) params.append('student_id', studentId);
        if (scanType) params.append('scan_type', scanType);
        if (result) params.append('result', result);
        if (dateFrom) params.append('date_from', `${dateFrom}T00:00:00`);
        if (dateTo) params.append('date_to', `${dateTo}T23:59:59`);

        const response = await apiFetch(`/api/logs/search?${params}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) throw new Error('Search failed');

        const data = await response.json();
        allLogs = (data.logs || []).map(normalizeLog);

        renderLogs(allLogs);

        console.log(`🔍 Search returned ${allLogs.length} results`);
    } catch (error) {
        console.error('❌ Error applying filters:', error);
        alert('Failed to apply filters');
    }
}

function clearFilters() {
    document.getElementById('searchStudent').value = '';
    document.getElementById('filterType').value = '';
    document.getElementById('filterResult').value = '';
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';

    loadRecentLogs();
}

// ============================================================================
// EXPORT
// ============================================================================

function exportLogs() {
    if (!allLogs || allLogs.length === 0) {
        alert('No logs to export');
        return;
    }

    // Create CSV content
    const headers = ['Timestamp', 'Student ID', 'Student Name', 'Type', 'Result', 'Gate', 'Details'];
    const rows = allLogs.map(rawLog => {
        const log = normalizeLog(rawLog);
        return [
            log.timestamp,
            log.student_id,
            log.student_name,
            log.scan_type,
            log.result,
            log.gate,
            log.details || ''
        ];
    });

    const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    // Download file
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `entry-exit-logs-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    console.log('📥 Exported', allLogs.length, 'logs to CSV');
}
