// popup.js — Password Vault browser extension popup logic

const API_BASE = "http://127.0.0.1:19815";

// State
let sessionToken = null;
let currentEntry = null;
let allEntries = [];

// DOM elements
const statusEl = document.getElementById("status");
const loginForm = document.getElementById("loginForm");
const entryList = document.getElementById("entryList");
const entryDetail = document.getElementById("entryDetail");
const masterPwInput = document.getElementById("masterPassword");
const unlockBtn = document.getElementById("unlockBtn");
const searchInput = document.getElementById("searchInput");
const entriesContainer = document.getElementById("entriesContainer");
const backBtn = document.getElementById("backBtn");
const logoutBtn = document.getElementById("logoutBtn");
const autofillBtn = document.getElementById("autofillBtn");
const togglePwBtn = document.getElementById("togglePwBtn");

// Views
function showView(view) {
  loginForm.classList.remove("active");
  entryList.classList.remove("active");
  entryDetail.classList.remove("active");
  view.classList.add("active");
}

function showStatus(message, type) {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

function hideStatus() {
  statusEl.className = "status";
}

// API calls
async function apiCall(method, path, body = null) {
  const headers = { "Content-Type": "application/json" };
  if (sessionToken) {
    headers["Authorization"] = `Bearer ${sessionToken}`;
  }

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const resp = await fetch(`${API_BASE}${path}`, opts);
  const data = await resp.json();

  if (!resp.ok) {
    throw new Error(data.error || `HTTP ${resp.status}`);
  }

  return data;
}

// Unlock vault
async function unlockVault() {
  const password = masterPwInput.value;
  if (!password) {
    showStatus("Enter your master password", "error");
    return;
  }

  unlockBtn.disabled = true;
  unlockBtn.textContent = "Unlocking...";

  try {
    const data = await apiCall("POST", "/auth", { password });
    sessionToken = data.token;
    allEntries = data.entries || [];

    // Save token for this session
    chrome.storage.session.set({ sessionToken, allEntries });

    showStatus(`Unlocked — ${allEntries.length} entries`, "success");
    setTimeout(hideStatus, 2000);

    renderEntries(allEntries);
    showView(entryList);
    searchInput.focus();
  } catch (err) {
    showStatus(err.message, "error");
  } finally {
    unlockBtn.disabled = false;
    unlockBtn.textContent = "Unlock Vault";
    masterPwInput.value = "";
  }
}

// Render entry list
function renderEntries(entries) {
  entriesContainer.innerHTML = "";

  if (entries.length === 0) {
    entriesContainer.innerHTML = '<div style="text-align:center;color:#888;padding:20px">No entries found</div>';
    return;
  }

  entries.forEach(name => {
    const item = document.createElement("div");
    item.className = "entry-item";
    item.innerHTML = `
      <div class="entry-icon">${name.charAt(0).toUpperCase()}</div>
      <div class="entry-name">${name}</div>
    `;
    item.addEventListener("click", () => selectEntry(name));
    entriesContainer.appendChild(item);
  });
}

// Search entries
function filterEntries(query) {
  if (!query) return allEntries;
  const q = query.toLowerCase();
  return allEntries.filter(name => name.toLowerCase().includes(q));
}

// Select entry
async function selectEntry(name) {
  try {
    const data = await apiCall("POST", "/entries", { name });
    currentEntry = data;

    document.getElementById("detailName").textContent = data.name;
    document.getElementById("detailUsername").textContent = data.username;
    document.getElementById("detailPassword").textContent = "••••••••";
    document.getElementById("detailPassword").classList.add("hidden");

    const urlGroup = document.getElementById("urlGroup");
    if (data.url) {
      document.getElementById("detailUrl").textContent = data.url;
      urlGroup.style.display = "block";
    } else {
      urlGroup.style.display = "none";
    }

    showView(entryDetail);
  } catch (err) {
    showStatus(err.message, "error");
  }
}

// Copy to clipboard
async function copyField(field) {
  if (!currentEntry) return;

  let text = "";
  if (field === "username") text = currentEntry.username;
  else if (field === "password") text = currentEntry.password;
  else if (field === "url") text = currentEntry.url;

  try {
    await navigator.clipboard.writeText(text);
    showStatus(`${field} copied — cleared in 30s`, "success");

    // Auto-clear after 30s
    setTimeout(async () => {
      const clipText = await navigator.clipboard.readText();
      if (clipText === text) {
        await navigator.clipboard.writeText("");
      }
    }, 30000);
  } catch {
    showStatus("Clipboard access denied", "error");
  }
}

// Toggle password visibility
function togglePassword() {
  const el = document.getElementById("detailPassword");
  if (el.classList.contains("hidden")) {
    el.textContent = currentEntry.password;
    el.classList.remove("hidden");
    togglePwBtn.textContent = "🙈";
  } else {
    el.textContent = "••••••••";
    el.classList.add("hidden");
    togglePwBtn.textContent = "👁";
  }
}

// Autofill on current tab
async function autofillOnPage() {
  if (!currentEntry) return;

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await chrome.tabs.sendMessage(tab.id, {
      action: "autofill",
      username: currentEntry.username,
      password: currentEntry.password,
    });
    showStatus("Credentials filled!", "success");
    setTimeout(() => window.close(), 1000);
  } catch (err) {
    showStatus("Autofill failed — no matching form found", "error");
  }
}

// Logout
async function logout() {
  try {
    if (sessionToken) {
      await apiCall("DELETE", "/session");
    }
  } catch { /* ignore */ }

  sessionToken = null;
  currentEntry = null;
  allEntries = [];
  chrome.storage.session.clear();
  showView(loginForm);
  showStatus("Vault locked", "info");
  setTimeout(hideStatus, 2000);
}

// Event listeners
unlockBtn.addEventListener("click", unlockVault);
masterPwInput.addEventListener("keydown", e => { if (e.key === "Enter") unlockVault(); });

searchInput.addEventListener("input", e => {
  renderEntries(filterEntries(e.target.value));
});

backBtn.addEventListener("click", () => {
  currentEntry = null;
  showView(entryList);
  searchInput.focus();
});

logoutBtn.addEventListener("click", logout);
autofillBtn.addEventListener("click", autofillOnPage);
togglePwBtn.addEventListener("click", togglePassword);

document.querySelectorAll(".copy-btn[data-field]").forEach(btn => {
  btn.addEventListener("click", () => copyField(btn.dataset.field));
});

// Restore session on popup open
(async () => {
  const stored = await chrome.storage.session.get(["sessionToken", "allEntries"]);
  if (stored.sessionToken) {
    sessionToken = stored.sessionToken;
    allEntries = stored.allEntries || [];

    try {
      // Verify session is still valid
      const data = await apiCall("GET", "/entries");
      allEntries = data.entries;
      renderEntries(allEntries);
      showView(entryList);
    } catch {
      // Session expired
      sessionToken = null;
      showView(loginForm);
    }
  }
})();
