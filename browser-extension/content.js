// content.js — Autofill credentials into login forms on the current page

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "autofill") {
    const result = autofillForm(message.username, message.password);
    sendResponse({ success: result });
  }
  return true;
});

function autofillForm(username, password) {
  // Find password fields — most reliable indicator of a login form
  const passwordFields = document.querySelectorAll('input[type="password"]');
  if (passwordFields.length === 0) return false;

  for (const pwField of passwordFields) {
    // Find the associated username field
    const form = pwField.closest("form");
    let usernameField = null;

    if (form) {
      // Look for username/email/text input in the same form
      usernameField = form.querySelector(
        'input[type="email"], ' +
        'input[type="text"][name*="user"], ' +
        'input[type="text"][name*="login"], ' +
        'input[type="text"][name*="email"], ' +
        'input[type="text"][id*="user"], ' +
        'input[type="text"][id*="login"], ' +
        'input[type="text"][id*="email"], ' +
        'input[autocomplete="username"], ' +
        'input[autocomplete="email"]'
      );

      // Fallback: any text input before the password field
      if (!usernameField) {
        const inputs = form.querySelectorAll('input[type="text"], input[type="email"]');
        for (const inp of inputs) {
          if (inp !== pwField) {
            usernameField = inp;
            break;
          }
        }
      }
    }

    // If no form, look globally near the password field
    if (!usernameField) {
      usernameField = document.querySelector(
        'input[type="email"], ' +
        'input[autocomplete="username"], ' +
        'input[name="username"], ' +
        'input[name="email"], ' +
        'input[id="username"], ' +
        'input[id="email"]'
      );
    }

    // Fill the fields
    if (usernameField) {
      setNativeValue(usernameField, username);
    }
    setNativeValue(pwField, password);

    // Highlight briefly to show autofill happened
    highlightField(pwField);
    if (usernameField) highlightField(usernameField);

    return true;
  }

  return false;
}

function setNativeValue(element, value) {
  // Use native setter to bypass React/Vue/Angular wrappers
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, "value"
  ).set;
  nativeInputValueSetter.call(element, value);

  // Dispatch events so frameworks detect the change
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
}

function highlightField(element) {
  const original = element.style.boxShadow;
  element.style.boxShadow = "0 0 0 2px #00d4aa";
  element.style.transition = "box-shadow 0.3s ease";
  setTimeout(() => {
    element.style.boxShadow = original;
  }, 1500);
}
