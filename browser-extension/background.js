// background.js — Service worker for the Password Vault extension

// Keep session token in memory (cleared when extension restarts)
let sessionToken = null;

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "setToken") {
    sessionToken = message.token;
    sendResponse({ ok: true });
  }

  if (message.action === "getToken") {
    sendResponse({ token: sessionToken });
  }

  if (message.action === "clearToken") {
    sessionToken = null;
    chrome.storage.session.clear();
    sendResponse({ ok: true });
  }

  return true;
});

// Clear session when extension is suspended
chrome.runtime.onSuspend.addListener(() => {
  sessionToken = null;
});
