// Extension configuration
const CONFIG = {
  // Backend API configuration
  // Default: localhost for development
  // Change this to your production URL when deploying
  BACKEND_BASE_URL: "https://prediscountable-rustily-emmalee.ngrok-free.dev",
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
