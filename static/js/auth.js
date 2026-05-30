// ── AUTH HELPERS ────────────────────────────────
const API = '/api';

function getToken() { return localStorage.getItem('ff_access'); }
function getRefresh() { return localStorage.getItem('ff_refresh'); }

function setTokens(access, refresh) {
  localStorage.setItem('ff_access', access);
  localStorage.setItem('ff_refresh', refresh);
}

function clearTokens() {
  localStorage.removeItem('ff_access');
  localStorage.removeItem('ff_refresh');
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let res = await fetch(`${API}${path}`, { ...options, headers });

  // Auto-refresh token on 401
  if (res.status === 401 && getRefresh()) {
    const refreshRes = await fetch(`${API}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: getRefresh() })
    });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      setTokens(data.access, getRefresh());
      headers['Authorization'] = `Bearer ${data.access}`;
      res = await fetch(`${API}${path}`, { ...options, headers });
    } else {
      clearTokens();
      window.location.href = '/login/';
      return;
    }
  }

  if (res.status === 401) {
    clearTokens();
    window.location.href = '/login/';
    return;
  }

  return res;
}

function logout() {
  clearTokens();
  window.location.href = '/login/';
}

// Redirect to login if not authenticated (skip on login page)
function requireAuth() {
  if (!window.location.pathname.includes('/login') && !getToken()) {
    window.location.href = '/login/';
  }
}

// Load current user info into sidebar
async function loadUserInfo() {
  if (!getToken()) return;
  try {
    const res = await apiFetch('/auth/profile/');
    if (res && res.ok) {
      const user = await res.json();
      const el = document.getElementById('userName');
      const av = document.getElementById('userAvatar');
      if (el) el.textContent = user.username;
      if (av) av.textContent = user.username[0].toUpperCase();
    }
  } catch (e) {}
}

// ── TOAST NOTIFICATIONS ──────────────────────────
function showToast(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3500);
}

// ── MODAL HELPERS ────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.add('open');
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});

// ── FORMAT HELPERS ───────────────────────────────
function formatDuration(seconds) {
  if (!seconds) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit'
  });
}

function statusBadge(status) {
  const map = {
    SUCCESS: 'badge-success', RUNNING: 'badge-running',
    PENDING: 'badge-pending', FAILED: 'badge-failed',
    SKIPPED: 'badge-skipped', CANCELLED: 'badge-cancelled'
  };
  return `<span class="badge ${map[status] || ''}">${status}</span>`;
}

// Run on every page
requireAuth();
loadUserInfo();
