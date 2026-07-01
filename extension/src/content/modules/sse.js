/**
 * Shared Server-Sent Events (SSE) stream parser.
 *
 * The backend streams `data: {json}` lines over a POST response. Both the
 * non-progress API call (api.js) and the progress tracker (progress.js) consume
 * that same wire format, so the read/decode/buffer/parse loop lives here once.
 *
 * @param {Response} response - fetch() response whose body is an SSE stream
 * @param {Object} handlers
 * @param {(event: Object) => void} handlers.onEvent - called per parsed data payload
 * @param {() => void} [handlers.onChunk] - called once per received chunk
 *        (used to reset read-timeouts)
 */
async function parseSSEStream(response, { onEvent, onChunk } = {}) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    if (onChunk) onChunk();

    buffer += decoder.decode(value, { stream: true });

    // Process complete SSE messages; keep any incomplete trailing line buffered.
    const lines = buffer.split("\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const eventData = JSON.parse(line.slice(6));
          if (onEvent) onEvent(eventData);
        } catch (e) {
          console.error("Failed to parse SSE event:", line, e);
        }
      }
    }
  }
}

// Export for global (content-script) and module (test) use.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseSSEStream };
} else {
  window.parseSSEStream = parseSSEStream;
}
