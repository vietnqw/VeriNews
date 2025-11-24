/**
 * Progress tracking for VeriNews verification with SSE streaming support
 * Handles real-time stage updates from backend and provides callbacks for UI updates
 */

/**
 * Vietnamese stage names
 */
const VIETNAMESE_STAGES = {
  query_extraction: "Làm sạch và trích xuất luận điểm chính",
  search: "Tìm kiếm các bài báo liên quan",
  evaluation: "Phân tích, so sánh bài đăng với bài báo liên quan",
  synthesis: "Hoàn thiện kết quả đánh giá",
};

/**
 * Stage order for progress tracking
 */
const STAGE_ORDER = ["query_extraction", "search", "evaluation", "synthesis"];

/**
 * ProgressTracker - Manages verification progress with SSE streaming
 */
class ProgressTracker {
  constructor(onStageUpdate, onProgressUpdate, onComplete, onError) {
    this.onStageUpdate = onStageUpdate;
    this.onProgressUpdate = onProgressUpdate;
    this.onComplete = onComplete;
    this.onError = onError;

    // Track state
    this.stages = {};
    this.currentStage = null;
    this.completedStages = new Set();
    this.startTime = null;
    this.elapsedSeconds = 0;
    this.eventSource = null;
    this.abortController = null;
    this.isStreaming = false;

    // Initialize stage states
    STAGE_ORDER.forEach((stage) => {
      this.stages[stage] = {
        name: VIETNAMESE_STAGES[stage],
        status: "pending",
        startTime: null,
        endTime: null,
      };
    });
  }

  /**
   * Start SSE streaming verification
   * @param {string} content - Text content to verify
   * @param {boolean} cacheBypass - Force cache bypass
   */
  startStreaming(content, cacheBypass = false) {
    this.startTime = Date.now();
    this.isStreaming = true;
    this.completedStages.clear();

    // Emit initial state
    this.onProgressUpdate({
      currentStage: this.currentStage,
      stages: this.stages,
      progressPercent: 0,
      elapsedSeconds: 0,
    });

    // Build URL with stream parameter
    const url = new URL(`${CONFIG.BACKEND_BASE_URL}/api/v1/verify`);
    url.searchParams.append("stream", "true");

    // Prepare request body
    const requestBody = JSON.stringify({
      text: content,
      cache_bypass: cacheBypass,
    });

    // Try to open SSE connection
    try {
      const eventSource = new EventSource(
        `${CONFIG.BACKEND_BASE_URL}/api/v1/verify?stream=true`,
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      // EventSource doesn't support custom bodies in GET, so we need to use fetch with proper SSE handling
      this._streamWithFetch(content, cacheBypass);
    } catch (error) {
      console.warn("SSE not available, falling back to non-streaming:", error);
      this.streamingFallback(content, cacheBypass);
    }
  }

  /**
   * Fetch-based SSE streaming (works with POST)
   */
  async _streamWithFetch(content, cacheBypass) {
    // Create AbortController for timeout handling
    this.abortController = new AbortController();
    const { signal } = this.abortController;

    // Timeout configuration (in milliseconds)
    const INITIAL_TIMEOUT = 30000; // 30s for initial connection
    const READ_TIMEOUT = 60000; // 60s between stream chunks

    let receivedResult = false;

    try {
      // Set initial connection timeout
      const connectionTimeoutId = setTimeout(() => {
        if (!receivedResult) {
          this.abortController.abort();
        }
      }, INITIAL_TIMEOUT);

      const response = await fetch(
        `${CONFIG.BACKEND_BASE_URL}/api/v1/verify?stream=true`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            text: content,
            cache_bypass: cacheBypass,
          }),
          signal,
        }
      );

      clearTimeout(connectionTimeoutId);

      if (!response.ok) {
        this.onError({
          message: `Stream connection failed with status ${response.status}`,
        });
        return;
      }

      // Read streaming response
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let readTimeoutId = null;

      // Helper to reset read timeout
      const resetReadTimeout = () => {
        if (readTimeoutId) clearTimeout(readTimeoutId);
        readTimeoutId = setTimeout(() => {
          if (!receivedResult) {
            console.error("Stream read timeout - server may be down");
            reader.cancel();
            this.abortController.abort();
          }
        }, READ_TIMEOUT);
      };

      resetReadTimeout();

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          clearTimeout(readTimeoutId);
          break;
        }

        // Reset timeout on each chunk received
        resetReadTimeout();

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split("\n");
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const eventData = JSON.parse(line.slice(6));
              if (eventData.type === "result") {
                receivedResult = true;
              }
              this._handleStreamEvent(eventData);
            } catch (e) {
              console.error("Failed to parse SSE event:", line, e);
            }
          }
        }
      }

      // Check if stream ended without receiving a result
      if (!receivedResult) {
        this.onError({
          message: "Kết nối bị ngắt trước khi nhận được kết quả. Vui lòng thử lại.",
        });
      }
    } catch (error) {
      console.error("Streaming error:", error);

      // Provide user-friendly error messages
      let message = "Mất kết nối trong quá trình xác minh. Vui lòng thử lại.";
      if (error.name === "AbortError") {
        message = "Hết thời gian chờ phản hồi từ máy chủ. Vui lòng thử lại.";
      } else if (error instanceof TypeError && error.message.includes("Failed to fetch")) {
        message = "Không thể kết nối đến máy chủ VeriNews. Vui lòng kiểm tra kết nối mạng.";
      }

      this.onError({ message });
    } finally {
      this.abortController = null;
    }
  }

  /**
   * Handle incoming SSE event
   */
  _handleStreamEvent(eventData) {
    switch (eventData.type) {
      case "stage_update":
        this._handleStageUpdate(eventData);
        break;
      case "result":
        this._handleResult(eventData);
        break;
      case "error":
        this.onError({
          message: eventData.message || "Unknown error occurred",
        });
        break;
    }
  }

  /**
   * Handle stage progress update
   */
  _handleStageUpdate(event) {
    const { stage, stage_name, status } = event;

    // Update stage state
    if (this.stages[stage]) {
      this.stages[stage].status = status;
      if (status === "in_progress") {
        this.stages[stage].startTime = Date.now();
        this.currentStage = stage;
      } else if (status === "completed") {
        this.stages[stage].endTime = Date.now();
        this.completedStages.add(stage);
      }
    }

    // Calculate progress percentage
    const progressPercent = Math.round(
      (this.completedStages.size / STAGE_ORDER.length) * 100
    );

    // Calculate elapsed seconds
    const elapsedSeconds = Math.floor((Date.now() - this.startTime) / 1000);

    // Notify UI
    this.onStageUpdate({
      stage,
      stage_name,
      status,
    });

    this.onProgressUpdate({
      currentStage: this.currentStage,
      stages: this.stages,
      progressPercent,
      elapsedSeconds,
    });
  }

  /**
   * Handle final result
   */
  _handleResult(event) {
    const { data } = event;
    this.isStreaming = false;

    // Adapt response to MVP format
    const adaptedResponse = adaptVeriNewsResponse(data);

    this.onComplete(adaptedResponse);
  }

  /**
   * Fallback to non-streaming mode (for browsers without SSE support)
   */
  async streamingFallback(content, cacheBypass) {
    console.log("Falling back to non-streaming verification...");

    // Emit all stages as in-progress/completed quickly
    for (const stage of STAGE_ORDER) {
      this.stages[stage].status = "in_progress";
      const elapsedSeconds = Math.floor((Date.now() - this.startTime) / 1000);

      this.onStageUpdate({
        stage: stage,
        stage_name: this.stages[stage].name,
        status: "in_progress"
      });

      this.onProgressUpdate({
        currentStage: stage,
        stages: this.stages,
        progressPercent: Math.round((STAGE_ORDER.indexOf(stage) / STAGE_ORDER.length) * 100),
        elapsedSeconds,
      });

      await this.sleep(300); // Brief delay between stages

      this.stages[stage].status = "completed";
      this.completedStages.add(stage);
      const percentComplete = Math.round(
        (this.completedStages.size / STAGE_ORDER.length) * 100
      );

      this.onStageUpdate({
        stage: stage,
        stage_name: this.stages[stage].name,
        status: "completed"
      });

      this.onProgressUpdate({
        currentStage: stage,
        stages: this.stages,
        progressPercent: percentComplete,
        elapsedSeconds: Math.floor((Date.now() - this.startTime) / 1000),
      });
    }

    // Call standard API
    try {
      const response = await fetch(
        `${CONFIG.BACKEND_BASE_URL}/api/v1/verify?stream=false`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            text: content,
            cache_bypass: cacheBypass,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        this.onError({
          message:
            errorData.detail ||
            `API error: ${response.status}`,
        });
        return;
      }

      const veriNewsData = await response.json();
      const adaptedResponse = adaptVeriNewsResponse(veriNewsData);
      this.onComplete(adaptedResponse);
    } catch (error) {
      this.onError({
        message: "Xác minh nội dung thất bại. Vui lòng thử lại.",
      });
    }
  }

  /**
   * Utility: sleep function
   */
  sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Stop streaming (if still active)
   */
  stop() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    // Abort any ongoing fetch request
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    this.isStreaming = false;
  }

  /**
   * Get current progress state
   */
  getState() {
    return {
      stages: this.stages,
      currentStage: this.currentStage,
      progressPercent:
        (this.completedStages.size / STAGE_ORDER.length) * 100,
      elapsedSeconds: Math.floor((Date.now() - this.startTime) / 1000),
      isStreaming: this.isStreaming,
    };
  }
}

/**
 * Create and return a new ProgressTracker instance
 */
function createProgressTracker(onStageUpdate, onProgressUpdate, onComplete, onError) {
  return new ProgressTracker(
    onStageUpdate,
    onProgressUpdate,
    onComplete,
    onError
  );
}
