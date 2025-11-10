// --- SCRIPT INITIALIZATION & CLEANUP ---
// This block runs every time the script is injected.
// It ensures that when the extension is reloaded during development,
// we clean up artifacts from the previous version of the script.

// 1. Disconnect any active MutationObserver from a previous script instance.
if (window.verinewsObserver) {
  window.verinewsObserver.disconnect();
}

// 2. Remove all UI elements (buttons, overlays, modals) created by a previous script.
document
  .querySelectorAll(
    ".vn-overlay, .vn-extract-button, .vn-modal-overlay, .vn-menu-button"
  )
  .forEach((el) => el.remove());

// 3. Remove the 'processed' attribute marker from all elements.
document
  .querySelectorAll(`[data-vnext-processed]`)
  .forEach((el) => el.removeAttribute("data-vnext-processed"));

function main(isEnabled) {
  if (isEnabled) {
    startObserver();
  } else {
    stopObserver();
  }
}

// --- INITIAL STATE CHECK & MESSAGE LISTENER --- (No changes here)
chrome.storage.local.get(["isEnabled"], function (result) {
  main(result.isEnabled || false);
});

chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
  if (request.command === "toggle") {
    main(request.isEnabled);
    return;
  }
});
