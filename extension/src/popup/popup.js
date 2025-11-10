// Load configuration from config.js
// CONFIG is already declared in config.js, so we just reference it

// DOM elements
let connectionStatus, statusIndicator, retryButton, toggleSwitch, lastCrawledSection, lastCrawledTime;

document.addEventListener("DOMContentLoaded", function () {
  // Check if CONFIG is available
  if (!window.CONFIG) {
    updateConnectionStatus("Lỗi cấu hình", "disconnected");
    return;
  }

  // Get DOM elements
  connectionStatus = document.getElementById("connectionStatus");
  statusIndicator = document.getElementById("statusIndicator");
  retryButton = document.getElementById("retryButton");
  toggleSwitch = document.getElementById("toggleSwitch");
  lastCrawledSection = document.getElementById("lastCrawledSection");
  lastCrawledTime = document.getElementById("lastCrawledTime");

  // Initialize connection check
  checkConnection();

  // Set up event listeners
  retryButton.addEventListener("click", checkConnection);

  // On Popup Load: Check storage and update the button
  chrome.storage.local.get(["isEnabled"], function (result) {
    const isEnabled = result.isEnabled || false;
    updateToggleSwitch(isEnabled);
  });

  // On Button Click: Update storage, update the button, and send a message
  toggleSwitch.addEventListener("change", function () {
    const newState = toggleSwitch.checked;

    // Save the new state
    chrome.storage.local.set({ isEnabled: newState }, function () {
      // Query for the active tab in the current window
      chrome.tabs.query(
        { active: true, currentWindow: true },
        function (tabs) {
          if (tabs[0]) {
            // Send a message to the content script in the active tab
            chrome.tabs
              .sendMessage(tabs[0].id, {
                command: "toggle",
                isEnabled: newState,
              })
              .catch((error) => {
                // Content script doesn't exist on this page (not Facebook)
                // This is expected behavior, so we don't need to show an error
                console.log("Content script not available on this page");
              });
          }
        }
      );
    });
  });

  function updateToggleSwitch(isEnabled) {
    toggleSwitch.checked = isEnabled;
  }
});

async function checkConnection() {
  updateConnectionStatus("Đang kiểm tra...", "checking");
  retryButton.disabled = true;

  try {
    const result = await chrome.runtime.sendMessage({
      type: "bg_health_check",
      config: {
        baseUrl: window.CONFIG.BACKEND_BASE_URL,
        healthEndpoint: window.CONFIG.HEALTH_ENDPOINT,
        apiKey: window.CONFIG.API_KEY,
        timeoutMs: window.CONFIG.CONNECTION_TIMEOUT,
      },
    });

    if (result && result.ok && String(result.status).toLowerCase() === "healthy") {
      updateConnectionStatus("Đã kết nối", "connected");
      // Update last crawled time if available
      if (result.last_crawled_at) {
        updateLastCrawledTime(result.last_crawled_at);
      }
    } else if (result && result.ok) {
      updateConnectionStatus("Backend không ổn định", "disconnected");
      hideLastCrawledTime();
    } else if (result && result.status === "timeout") {
      updateConnectionStatus("Hết thời gian chờ", "disconnected");
      hideLastCrawledTime();
    } else if (result && result.status === "no_connection") {
      updateConnectionStatus("Không có kết nối", "disconnected");
      hideLastCrawledTime();
    } else {
      updateConnectionStatus("Kết nối thất bại", "disconnected");
      hideLastCrawledTime();
    }
  } catch (error) {
    updateConnectionStatus("Kết nối thất bại", "disconnected");
    hideLastCrawledTime();
  } finally {
    retryButton.disabled = false;
  }
}

function updateConnectionStatus(text, status) {
  if (connectionStatus && statusIndicator) {
    connectionStatus.textContent = text;
    statusIndicator.className = `status-indicator ${status}`;
  }
}

function updateLastCrawledTime(isoTimestamp) {
  if (!lastCrawledSection || !lastCrawledTime) return;

  try {
    const date = new Date(isoTimestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    let timeAgo;
    if (diffMins < 1) {
      timeAgo = "Vừa xong";
    } else if (diffMins < 60) {
      timeAgo = `${diffMins} phút trước`;
    } else if (diffHours < 24) {
      timeAgo = `${diffHours} giờ trước`;
    } else {
      timeAgo = `${diffDays} ngày trước`;
    }

    lastCrawledTime.textContent = timeAgo;
    lastCrawledTime.title = date.toLocaleString('vi-VN');
    lastCrawledSection.style.display = "block";
  } catch (error) {
    console.error("Error formatting last crawled time:", error);
    hideLastCrawledTime();
  }
}

function hideLastCrawledTime() {
  if (lastCrawledSection) {
    lastCrawledSection.style.display = "none";
  }
}
