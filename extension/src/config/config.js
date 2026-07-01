// Extension configuration
const CONFIG = {
  // Backend API configuration.
  // This is the ONLY place the backend location is configured — set it to
  // wherever your VeriNews backend is running.
  //   - Local dev:      http://localhost:8000
  //   - Tunnel/hosted:  https://<your-host>
  BACKEND_BASE_URL: "http://localhost:8000",
  HEALTH_ENDPOINT: "/api/v1/health",

  // Connection timeout in milliseconds
  CONNECTION_TIMEOUT: 5000,

  // Retry configuration
  MAX_RETRIES: 3,
  RETRY_DELAY: 1000,
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CONFIG;
} else {
  window.CONFIG = CONFIG;
}
