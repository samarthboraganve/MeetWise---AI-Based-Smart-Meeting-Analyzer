/**
 * app.js — Shared utilities for MeetWise AI frontend.
 * Loaded on every page.
 */

// ── XSS protection ──
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ── Toast Notifications ──
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = { success: '✓', error: '✗', info: 'ℹ' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${escapeHtml(message)}`;

    container.appendChild(toast);

    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 300ms ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ── API helper ──
async function apiCall(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: {}
    };

    if (body) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }

    const res = await fetch(url, options);
    if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Request failed: ${res.status}`);
    }
    return res.json();
}

// ── Session helpers ──
function getSession(key) {
    return sessionStorage.getItem(key);
}

function setSession(key, value) {
    sessionStorage.setItem(key, value);
}

// ── Format helpers ──
function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        return new Date(dateStr).toLocaleDateString('en-IN', {
            year: 'numeric', month: 'short', day: 'numeric'
        });
    } catch {
        return dateStr;
    }
}

// ── Console branding ──
console.log(
    '%c MeetWise AI %c Meetings end. Clarity begins.',
    'background: #4f8ff7; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;',
    'color: #888; padding: 4px;'
);
