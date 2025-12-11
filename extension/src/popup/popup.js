const STATUS = {
  CONNECTED: "connected",
  DISCONNECTED: "disconnected",
  CHECKING: "checking",
};

document.addEventListener("DOMContentLoaded", () => {
  if (!window.CONFIG) {
    renderConnection({ text: "Lỗi cấu hình", status: STATUS.DISCONNECTED });
    return;
  }

  const ui = initUi();
  bindEvents(ui);
  syncToggleState(ui);
  runHealthCheck(ui);
});

function initUi() {
  return {
    connectionStatus: document.getElementById("connectionStatus"),
    statusIndicator: document.getElementById("statusIndicator"),
    retryButton: document.getElementById("retryButton"),
    toggleSwitch: document.getElementById("toggleSwitch"),
    lastCrawledSection: document.getElementById("lastCrawledSection"),
    lastCrawledTime: document.getElementById("lastCrawledTime"),
  };
}

function bindEvents(ui) {
  ui.retryButton.addEventListener("click", () => runHealthCheck(ui));
  ui.toggleSwitch.addEventListener("change", () => handleToggleChange(ui));
}

function syncToggleState(ui) {
  chrome.storage.local.get(["isEnabled"], (result) => {
    const isEnabled = Boolean(result.isEnabled);
    ui.toggleSwitch.checked = isEnabled;
  });
}

function handleToggleChange(ui) {
  const isEnabled = ui.toggleSwitch.checked;

  chrome.storage.local.set({ isEnabled }, () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]) return;

      chrome.tabs
        .sendMessage(tabs[0].id, { command: "toggle", isEnabled })
        .catch(() => {
          // Content script may be absent on some pages; safe to ignore.
          console.log("Content script not available on this page");
        });
    });
  });
}

async function runHealthCheck(ui) {
  renderConnection({ text: "Đang kiểm tra...", status: STATUS.CHECKING, ui });
  ui.retryButton.disabled = true;

  try {
    const result = await chrome.runtime.sendMessage({
      type: "bg_health_check",
      config: {
        baseUrl: window.CONFIG.BACKEND_BASE_URL,
        healthEndpoint: window.CONFIG.HEALTH_ENDPOINT,
        timeoutMs: window.CONFIG.CONNECTION_TIMEOUT,
      },
    });

    handleHealthResponse({ result, ui });
  } catch (error) {
    renderConnection({ text: "Kết nối thất bại", status: STATUS.DISCONNECTED, ui });
    hideLastCrawledTime(ui);
  } finally {
    ui.retryButton.disabled = false;
  }
}

function handleHealthResponse({ result, ui }) {
  if (!result) {
    renderConnection({ text: "Kết nối thất bại", status: STATUS.DISCONNECTED, ui });
    hideLastCrawledTime(ui);
    return;
  }

  const status = String(result.status || "").toLowerCase();

  if (result.ok && status === "healthy") {
    renderConnection({ text: "Đã kết nối", status: STATUS.CONNECTED, ui });
    if (result.last_crawled_at) renderLastCrawledTime(result.last_crawled_at, ui);
    return;
  }

  const fallbackMessages = {
    timeout: "Hết thời gian chờ",
    no_connection: "Không có kết nối",
  };

  const text = fallbackMessages[result.status] || (result.ok ? "Backend không ổn định" : "Kết nối thất bại");
  renderConnection({ text, status: STATUS.DISCONNECTED, ui });
  hideLastCrawledTime(ui);
}

function renderConnection({ text, status, ui }) {
  const connectionStatus = ui?.connectionStatus || document.getElementById("connectionStatus");
  const statusIndicator = ui?.statusIndicator || document.getElementById("statusIndicator");
  if (!connectionStatus || !statusIndicator) return;

  connectionStatus.textContent = text;
  statusIndicator.className = `status-indicator ${status}`;
}

function renderLastCrawledTime(isoTimestamp, ui) {
  const { lastCrawledSection, lastCrawledTime } = ui;
  if (!lastCrawledSection || !lastCrawledTime) return;

  try {
    const date = new Date(isoTimestamp);
    const diffMs = Date.now() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    const timeAgo =
      diffMins < 1
        ? "Vừa xong"
        : diffMins < 60
        ? `${diffMins} phút trước`
        : diffHours < 24
        ? `${diffHours} giờ trước`
        : `${diffDays} ngày trước`;

    lastCrawledTime.textContent = timeAgo;
    lastCrawledTime.title = date.toLocaleString("vi-VN");
    lastCrawledSection.style.display = "block";
  } catch (error) {
    console.error("Error formatting last crawled time:", error);
    hideLastCrawledTime(ui);
  }
}

function hideLastCrawledTime(ui) {
  const lastCrawledSection = ui?.lastCrawledSection || document.getElementById("lastCrawledSection");
  if (!lastCrawledSection) return;
  lastCrawledSection.style.display = "none";
}
