// Centralized health check in background (MV3 service worker)

function getTimeoutSignal(ms) {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(ms);
  }
  const controller = new AbortController();
  setTimeout(() => {
    try {
      controller.abort();
    } catch (_) {}
  }, ms);
  return controller.signal;
}

async function performHealthCheck(config) {
  const { baseUrl, healthEndpoint, timeoutMs } = config;
  try {
    // Only send the ngrok bypass header when the backend is actually behind an
    // ngrok tunnel; harmless to omit for localhost/other hosts.
    const headers = {};
    if (baseUrl && baseUrl.includes("ngrok")) {
      headers["ngrok-skip-browser-warning"] = "true";
    }
    const res = await fetch(`${baseUrl}${healthEndpoint}`, {
      method: "GET",
      headers,
      cache: "no-store",
      signal: getTimeoutSignal(timeoutMs || 5000),
    });
    if (!res.ok) return { ok: false, status: "backend_error", code: res.status };

    // Parse JSON if possible; otherwise treat 200 OK as connected
    let data = null;
    try {
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("json")) data = await res.json();
    } catch (_) {}

    if (data && typeof data.status === "string") {
      return {
        ok: true,
        status: data.status.toLowerCase(),
        last_crawled_at: data.last_crawled_at,
        pgvector: data.pgvector,
        database: data.database,
        api: data.api
      };
    }
    return { ok: true, status: "healthy" };
  } catch (e) {
    const msg = (e && e.message ? String(e.message) : "").toLowerCase();
    if (e.name === "AbortError" || e.name === "TimeoutError" || msg.includes("timeout")) {
      return { ok: false, status: "timeout" };
    }
    if (e.name === "TypeError" && msg.includes("failed to fetch")) {
      return { ok: false, status: "no_connection" };
    }
    return { ok: false, status: "failed" };
  }
}

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  if (request && request.type === "bg_health_check") {
    (async () => {
      const result = await performHealthCheck(request.config || {});
      sendResponse(result);
    })();
    return true; // keep channel open
  }
});
