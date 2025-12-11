const VN_ICON_NS = "http://www.w3.org/2000/svg";

function createSvgElement(tag, attrs = {}) {
  const el = document.createElementNS(VN_ICON_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  if (tag !== "svg") {
    if (!attrs.fill) el.setAttribute("fill", "none");
    if (!attrs.stroke && attrs.fill !== "currentColor") el.setAttribute("stroke", "currentColor");
    if (!attrs["stroke-width"] && attrs.fill !== "currentColor") el.setAttribute("stroke-width", "1.8");
    el.setAttribute("stroke-linecap", attrs["stroke-linecap"] || "round");
    el.setAttribute("stroke-linejoin", attrs["stroke-linejoin"] || "round");
  }
  return el;
}

const VN_ICON_BUILDERS = {
  success: (svg) => {
    svg.appendChild(createSvgElement("circle", { cx: "12", cy: "12", r: "9" }));
    svg.appendChild(createSvgElement("polyline", { points: "7.5 12.5 10.5 15.5 16.5 9.5" }));
  },
  danger: (svg) => {
    svg.appendChild(createSvgElement("circle", { cx: "12", cy: "12", r: "9" }));
    svg.appendChild(createSvgElement("line", { x1: "9", y1: "9", x2: "15", y2: "15" }));
    svg.appendChild(createSvgElement("line", { x1: "15", y1: "9", x2: "9", y2: "15" }));
  },
  warning: (svg) => {
    svg.appendChild(createSvgElement("polygon", { points: "12 4 20 19 4 19" }));
    svg.appendChild(createSvgElement("line", { x1: "12", y1: "10", x2: "12", y2: "14.5" }));
    svg.appendChild(createSvgElement("circle", { cx: "12", cy: "16.8", r: "0.6", fill: "currentColor", stroke: "none" }));
  },
  info: (svg) => {
    svg.appendChild(createSvgElement("circle", { cx: "12", cy: "12", r: "9" }));
    svg.appendChild(createSvgElement("line", { x1: "12", y1: "11", x2: "12", y2: "16" }));
    svg.appendChild(createSvgElement("circle", { cx: "12", cy: "7.5", r: "0.6", fill: "currentColor", stroke: "none" }));
  },
  link: (svg) => {
    // Material Symbols "link" icon - chain links
    const path = createSvgElement("path", { d: "M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z" });
    path.setAttribute("fill", "currentColor");
    path.setAttribute("stroke", "none");
    svg.appendChild(path);
  },
  checklist: (svg) => {
    // Material Symbols "checklist" icon - clipboard with checkmarks
    const path = createSvgElement("path", { d: "M19 3h-4.18C14.4 1.84 13.3 1 12 1s-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm-2 14l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z" });
    path.setAttribute("fill", "currentColor");
    path.setAttribute("stroke", "none");
    svg.appendChild(path);
  },
  analytics: (svg) => {
    // Material Symbols "analytics" icon - bar chart
    const path = createSvgElement("path", { d: "M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z" });
    path.setAttribute("fill", "currentColor");
    path.setAttribute("stroke", "none");
    svg.appendChild(path);
  },
  article: (svg) => {
    // Material Symbols "article" icon - document
    const path = createSvgElement("path", { d: "M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z" });
    path.setAttribute("fill", "currentColor");
    path.setAttribute("stroke", "none");
    svg.appendChild(path);
  },
  "chevron-down": (svg) => {
    svg.appendChild(createSvgElement("polyline", { points: "6 10 12 16 18 10" }));
  },
  "chevron-right": (svg) => {
    svg.appendChild(createSvgElement("polyline", { points: "10 6 16 12 10 18" }));
  }
};

function createIcon(name, extraClass = "") {
  const svg = createSvgElement("svg", { viewBox: "0 0 24 24", focusable: "false", role: "img", "aria-hidden": "true" });
  svg.classList.add("vn-icon");
  if (extraClass) {
    extraClass.split(" ").filter(Boolean).forEach(cls => svg.classList.add(cls));
  }
  const builder = VN_ICON_BUILDERS[name] || VN_ICON_BUILDERS.info;
  builder(svg);
  return svg;
}

/**
 * Creates the enhanced progress loading UI with stages
 * @param {object} progressTracker - Progress tracker instance
 * @param {Function} onComplete - Callback when streaming completes
 * @param {Function} onError - Optional callback when an error occurs
 * @returns {HTMLElement} Progress container element
 */
function createProgressLoadingUI(progressTracker, onComplete, onError = null) {
  const progressContainer = document.createElement("div");
  progressContainer.className = "vn-progress-loading-container";

  // Stages definition
  const stages = [
    { key: "query_extraction", short: "Trích xuất", name: "Làm sạch và trích xuất luận điểm chính" },
    { key: "search", short: "Tìm kiếm", name: "Tìm kiếm các bài báo liên quan" },
    { key: "evaluation", short: "Đánh giá", name: "Phân tích, so sánh bài đăng với bài báo liên quan" },
    { key: "synthesis", short: "Tổng hợp", name: "Hoàn thiện kết quả đánh giá" },
  ];

  // Progress Bar Wrapper
  const barWrapper = document.createElement("div");
  barWrapper.className = "vn-progress-bar-wrapper";

  const barContainer = document.createElement("div");
  barContainer.className = "vn-progress-bar-container";

  const barBackground = document.createElement("div");
  barBackground.className = "vn-progress-bar-background";

  const barFill = document.createElement("div");
  barFill.className = "vn-progress-bar-fill";
  // Initialize width to 0
  barFill.style.width = "0%";

  barContainer.appendChild(barBackground);
  barContainer.appendChild(barFill);

  // Create Checkpoints
  const checkpoints = [];
  stages.forEach((stage, index) => {
    const checkpoint = document.createElement("div");
    checkpoint.className = "vn-progress-checkpoint";
    // Calculate position: distribute evenly 0% to 100%
    const leftPos = (index / (stages.length - 1)) * 100;
    checkpoint.style.left = `${leftPos}%`;

    const dot = document.createElement("div");
    dot.className = "vn-progress-dot";

    const label = document.createElement("div");
    label.className = "vn-progress-checkpoint-label";
    label.innerText = stage.short;

    checkpoint.appendChild(dot);
    checkpoint.appendChild(label);
    barContainer.appendChild(checkpoint);

    checkpoints.push({ key: stage.key, element: checkpoint, pos: leftPos });
  });

  barWrapper.appendChild(barContainer);

  // Stage Name Display (Full Name)
  const stageNameDisplay = document.createElement("h2");
  stageNameDisplay.className = "vn-progress-stage-name animate-in"; // Add initial animation
  stageNameDisplay.innerText = stages[0].name; // Initial text

  progressContainer.appendChild(barWrapper);
  progressContainer.appendChild(stageNameDisplay);

  // Set up callbacks
  progressTracker.onStageUpdate = (event) => {
    const { stage, stage_name, status } = event;

    const index = stages.findIndex(s => s.key === stage);

    if (index !== -1) {
      // Update stage text with animation reset
      if (stageNameDisplay.innerText !== stages[index].name) {
        stageNameDisplay.classList.remove("animate-in");
        void stageNameDisplay.offsetWidth; // Trigger reflow to restart animation
        stageNameDisplay.innerText = stages[index].name;
        stageNameDisplay.classList.add("animate-in");
      }

      // Update bar width
      // If status is 'in_progress', we are AT this checkpoint.
      // If 'completed', we might be moving past it, but usually the next stage 'in_progress' handles that.

      const percent = (index / (stages.length - 1)) * 100;
      barFill.style.width = `${percent}%`;

      // Update checkpoints
      checkpoints.forEach((cp, i) => {
        cp.element.classList.remove("active", "completed", "pending");
        if (i < index) {
          cp.element.classList.add("completed");
        } else if (i === index) {
          if (status === "completed") {
             cp.element.classList.add("completed");
          } else {
             cp.element.classList.add("active");
          }
        } else {
          cp.element.classList.add("pending");
        }
      });
    }
  };

  // We ignore onProgressUpdate as requested (no percentages)
  progressTracker.onProgressUpdate = (progress) => {
     // Optional: Smooth interpolation between checkpoints could go here if we wanted
     // but for now we stick to the checkpoints.
  };

  progressTracker.onComplete = (response) => {
    // Fill bar to 100% on complete
    barFill.style.width = "100%";
    checkpoints.forEach(cp => {
        cp.element.classList.remove("active", "pending");
        cp.element.classList.add("completed");
    });

    // Small delay before removing to show completion state
    setTimeout(() => {
        if (progressContainer.parentElement) {
          progressContainer.remove();
        }
        if (onComplete) {
          onComplete(response);
        }
    }, 500);
  };

  // Store the original onError callback before overwriting
  const originalOnError = progressTracker.onError;

  progressTracker.onError = (error) => {
    progressContainer.innerHTML = `
      <div style="text-align: center; padding: 32px 24px;">
        <h3 style="color: #ef4444; margin-bottom: 12px; font-size: 18px;">Xác minh thất bại</h3>
        <p style="color: #666; font-size: 15px; line-height: 1.5;">${error.message}</p>
      </div>
    `;
    // Call the original onError callback to re-enable the button
    if (originalOnError) {
      originalOnError(error);
    }
    // Also call the onError parameter if provided
    if (onError) {
      onError(error);
    }
  };

  return progressContainer;
}

/**
 * Displays a modal popup with the extracted content or verification result.
 * @param {string} content - Text content to verify.
 * @param {object | null} apiResponse - Verification API response or null while loading.
 * @param {object | null} progressTracker - Optional progress tracker for streaming mode.
 * @param {Function | null} onComplete - Callback when streaming completes.
 */
function showContentPopup(content, apiResponse, progressTracker = null, onComplete = null) {
  const overlay = document.createElement("div");
  overlay.className = "vn-modal-overlay";

  const modal = document.createElement("div");
  modal.className = "vn-modal-content";

  const closeButton = document.createElement("button");
  closeButton.className = "vn-modal-close";
  modal.appendChild(closeButton);

  const { showTooltip, hideTooltip } = createTooltipManager();

  const createCollapsibleSection = (title, contentElement, isCollapsed = true) => {
    const iconMap = {
      "Bài báo liên quan": "link",
      "Điểm chi tiết": "checklist",
      "Phân tích chi tiết": "analytics",
      "Nội dung bài đăng": "article"
    };

    const section = document.createElement("details");
    section.className = "vn-details-section";
    if (!isCollapsed) section.setAttribute("open", "");

    const summary = document.createElement("summary");
    summary.className = "vn-details-summary";

    const summaryLeft = document.createElement("div");
    summaryLeft.className = "vn-details-summary-left";

    const icon = createIcon(iconMap[title] || "info", "vn-details-icon");
    const titleSpan = document.createElement("span");
    titleSpan.className = "vn-details-title";
    titleSpan.innerText = title;

    summaryLeft.appendChild(icon);
    summaryLeft.appendChild(titleSpan);

    const chevron = createIcon("chevron-down", "vn-details-chevron");
    summary.appendChild(summaryLeft);
    summary.appendChild(chevron);

    const contentWrapper = document.createElement("div");
    contentWrapper.className = "vn-details-content";
    contentWrapper.appendChild(contentElement);

    section.appendChild(summary);
    section.appendChild(contentWrapper);
    return section;
  };

  if (!apiResponse) {
    renderLoadingState({ modal, progressTracker, onComplete });
  } else if (apiResponse.error) {
    renderErrorState({ modal, message: apiResponse.message });
  } else {
    renderResultView({
      modal,
      content,
      apiResponse,
      createCollapsibleSection,
      showTooltip,
      hideTooltip
    });
  }

  if (apiResponse && !apiResponse.error && apiResponse._veriNewsMetadata) {
    modal.appendChild(createFooter({ apiResponse, content }));
  }

  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  const closeModal = () => document.body.removeChild(overlay);
  closeButton.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
}

function createTooltipManager() {
  let activeTooltip = null;

  const showTooltip = (target, text) => {
    if (activeTooltip) activeTooltip.remove();

    const tooltip = document.createElement("div");
    tooltip.className = "vn-floating-tooltip";
    tooltip.innerHTML = text;
    document.body.appendChild(tooltip);
    activeTooltip = tooltip;

    const rect = target.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();

    let top = rect.top - tooltipRect.height - 10;
    let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);

    if (left < 10) left = 10;
    if (left + tooltipRect.width > window.innerWidth - 10) {
      left = window.innerWidth - tooltipRect.width - 10;
    }

    if (top < 10) {
      top = rect.bottom + 10;
      tooltip.classList.add("bottom");
    }

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;

    requestAnimationFrame(() => tooltip.classList.add("visible"));
  };

  const hideTooltip = () => {
    if (!activeTooltip) return;
    activeTooltip.classList.remove("visible");
    const tooltipToRemove = activeTooltip;
    activeTooltip = null;
    setTimeout(() => { if (tooltipToRemove.parentNode) tooltipToRemove.remove(); }, 200);
  };

  return { showTooltip, hideTooltip };
}

function renderLoadingState({ modal, progressTracker, onComplete }) {
  if (progressTracker) {
    const progressContainer = createProgressLoadingUI(progressTracker, onComplete);
    modal.appendChild(progressContainer);
    return;
  }

  const loadingContainer = document.createElement("div");
  loadingContainer.className = "vn-loading-container";

  const spinnerWrapper = document.createElement("div");
  spinnerWrapper.className = "vn-loading-spinner-wrapper";

  const spinnerTrack = document.createElement("div");
  spinnerTrack.className = "vn-loading-spinner-track";

  const spinnerIndicator = document.createElement("div");
  spinnerIndicator.className = "vn-loading-spinner-indicator";

  spinnerWrapper.appendChild(spinnerTrack);
  spinnerWrapper.appendChild(spinnerIndicator);

  const loadingTitle = document.createElement("h1");
  loadingTitle.className = "vn-loading-title";
  loadingTitle.innerText = "Đang xác minh nội dung...";

  const loadingDescription = document.createElement("p");
  loadingDescription.className = "vn-loading-description";
  loadingDescription.innerText = "Vui lòng chờ trong giây lát. Quá trình này có thể mất một chút thời gian.";

  loadingContainer.appendChild(spinnerWrapper);
  loadingContainer.appendChild(loadingTitle);
  loadingContainer.appendChild(loadingDescription);
  modal.appendChild(loadingContainer);
}

function renderErrorState({ modal, message }) {
  const errorContainer = document.createElement("div");
  errorContainer.className = "vn-error-container";

  const errorTitle = document.createElement("h3");
  errorTitle.className = "vn-error-title";
  errorTitle.innerText = "Xác minh thất bại";

  const errorMessage = document.createElement("p");
  errorMessage.className = "vn-error-message";
  errorMessage.innerText = message;

  errorContainer.appendChild(errorTitle);
  errorContainer.appendChild(errorMessage);
  modal.appendChild(errorContainer);
}

function renderResultView({ modal, content, apiResponse, createCollapsibleSection, showTooltip, hideTooltip }) {
  const hero = createHeroSection(apiResponse);
  const sections = document.createElement("div");
  sections.className = "vn-result-body";

  sections.appendChild(createExplanationSection(apiResponse));
  sections.appendChild(createArticlesSection(apiResponse, createCollapsibleSection));

  const scoresSection = createScoresSection(apiResponse, createCollapsibleSection, showTooltip, hideTooltip);
  if (scoresSection) sections.appendChild(scoresSection);

  const claimsSection = createClaimAnalysisSection(apiResponse, createCollapsibleSection);
  if (claimsSection) sections.appendChild(claimsSection);

  sections.appendChild(createContentSection(content, createCollapsibleSection));

  const contextBanner = createContextBanner(apiResponse);
  if (contextBanner) sections.appendChild(contextBanner);

  modal.appendChild(hero);
  modal.appendChild(sections);
}

function createHeroSection(apiResponse) {
  const scorePercent = Math.round(apiResponse.final_score * 100);
  const decisionMap = {
    "Fully Supported": "Hoàn toàn chính xác",
    "Partially Supported": "Đúng một phần",
    "Refuted": "Sai lệch/Giả mạo",
    "Not Enough Info": "Chưa đủ thông tin",
    "Verified": "Đã xác minh",
    "Misleading/False": "Sai lệch/Giả mạo",
    "Out of Context": "Sai ngữ cảnh",
    "Unverified": "Chưa xác minh"
  };
  const themeMap = {
    green: { className: "success", icon: "success" },
    yellow: { className: "warning", icon: "warning" },
    red: { className: "danger", icon: "danger" },
    gray: { className: "neutral", icon: "info" }
  };

  const heroTheme = themeMap[apiResponse.flag] || themeMap.gray;
  const decisionLabel = decisionMap[apiResponse.overall_decision] || "Không rõ";

  const heroSection = document.createElement("section");
  heroSection.className = `vn-result-hero ${heroTheme.className}`;

  const heroBadge = document.createElement("div");
  heroBadge.className = "vn-hero-icon-circle";
  const heroIcon = createIcon(heroTheme.icon, "vn-icon-hero");
  heroBadge.appendChild(heroIcon);

  const heroTitle = document.createElement("h1");
  heroTitle.className = "vn-hero-title";
  heroTitle.innerText = decisionLabel;

  const heroConfidence = document.createElement("p");
  heroConfidence.className = "vn-hero-confidence";
  heroConfidence.innerText = `Độ tin cậy ${scorePercent}%`;

  heroSection.appendChild(heroBadge);
  heroSection.appendChild(heroTitle);
  heroSection.appendChild(heroConfidence);
  return heroSection;
}

function createExplanationSection(apiResponse) {
  const section = document.createElement("section");
  section.className = "vn-result-section";

  const heading = document.createElement("h2");
  heading.className = "vn-section-heading";
  heading.innerText = "Giải thích";

  const text = document.createElement("p");
  text.className = "vn-section-text";
  text.innerText = apiResponse.explanation && apiResponse.explanation.trim() !== ""
    ? apiResponse.explanation
    : "Hệ thống chưa cung cấp giải thích chi tiết cho kết quả này.";

  section.appendChild(heading);
  section.appendChild(text);
  return section;
}

function createArticlesSection(apiResponse, createCollapsibleSection) {
  const container = document.createElement("div");
  container.className = "vn-articles-section";
  const hasArticles = apiResponse.matched_articles && apiResponse.matched_articles.length > 0;

  if (hasArticles) {
    const list = document.createElement("div");
    list.className = "vn-related-list";
    apiResponse.matched_articles.forEach((article) => {
      const articleCard = document.createElement("a");
      articleCard.href = article.url;
      articleCard.target = "_blank";
      articleCard.rel = "noopener noreferrer";
      articleCard.className = "vn-related-article";

      const cardText = document.createElement("div");
      cardText.className = "vn-related-text";

      const title = document.createElement("p");
      title.className = "vn-related-title";
      title.innerText = article.title;

      const meta = document.createElement("p");
      meta.className = "vn-related-meta";
      const accuracy = Math.round(article.similarity * 100);
      meta.innerText = `${article.source} - Mức độ liên quan ${accuracy}%`;

      cardText.appendChild(title);
      cardText.appendChild(meta);

      const arrow = createIcon("chevron-right", "vn-related-chevron");

      articleCard.appendChild(cardText);
      articleCard.appendChild(arrow);
      list.appendChild(articleCard);
    });
    container.appendChild(list);
  } else {
    const emptyMessage = document.createElement("p");
    emptyMessage.className = "vn-empty-message";
    emptyMessage.innerText = "Không tìm thấy bài báo liên quan.";
    container.appendChild(emptyMessage);
  }

  return createCollapsibleSection("Bài báo liên quan", container, false);
}

function createScoresSection(apiResponse, createCollapsibleSection, showTooltip, hideTooltip) {
  if (!apiResponse.per_criterion_scores) return null;
  const scores = apiResponse.per_criterion_scores;
  const hasScores = scores.evidence_quality > 0 || scores.source_agreement > 0 ||
    scores.source_quantity > 0 || scores.temporal_relevance > 0;
  if (!hasScores) return null;

  const criterionDetails = document.createElement("div");
  const scoreItems = [
    {
      label: "Chất lượng bằng chứng",
      value: scores.evidence_quality,
      description: "Mức độ chắc chắn của hệ thống khi đưa ra kết luận về độ chính xác của các luận điểm trong bài đăng khi so sánh với các nguồn tin chính thống. Điểm cao nghĩa là các luận điểm được đánh giá với độ chính xác cao."
    },
    {
      label: "Mức độ đồng thuận nguồn tin",
      value: scores.source_agreement,
      description: "Cho biết các bài báo khác nhau đang cùng thống nhất về các luận điểm hay mâu thuẫn nhau. Điểm cao nghĩa là đa số nguồn tin uy tín cùng đưa ra thông tin giống nhau về các luận điểm đó."
    },
    {
      label: "Số lượng nguồn tin",
      value: scores.source_quantity,
      description: "Cho biết số lượng nguồn tin đáng tin cậy đã được sử dụng để xác minh. Điểm cao nghĩa là có nhiều nguồn tin khác nhau cùng cung cấp thông tin về các luận điểm này."
    },
    {
      label: "Độ mới của bài báo",
      value: scores.temporal_relevance,
      description: "Đo độ mới của các bài báo dùng để kiểm chứng. Điểm cao nghĩa là hệ thống chủ yếu dựa vào các bài báo gần đây, phù hợp với bối cảnh hiện tại."
    }
  ];

  scoreItems.forEach(item => {
    const row = document.createElement("div");
    row.className = "vn-score-row";

    const label = document.createElement("span");
    label.className = "vn-score-row-label";
    label.innerText = item.label;
    label.addEventListener("mouseenter", () => showTooltip(label, item.description));
    label.addEventListener("mouseleave", hideTooltip);
    label.addEventListener("click", (e) => { e.stopPropagation(); showTooltip(label, item.description); });

    const value = document.createElement("span");
    value.className = "vn-score-row-value";
    value.innerText = `${Math.round(item.value * 100)}%`;

    row.appendChild(label);
    row.appendChild(value);
    criterionDetails.appendChild(row);
  });

  return createCollapsibleSection("Điểm chi tiết", criterionDetails, false);
}

function createClaimAnalysisSection(apiResponse, createCollapsibleSection) {
  if (!apiResponse.claim_verdicts || apiResponse.claim_verdicts.length === 0) return null;

  const verdictInfo = {
    "SUPPORTED": { text: "Được hỗ trợ", color: "green", icon: "✓" },
    "REFUTED": { text: "Bị bác bỏ", color: "red", icon: "✗" },
    "NOT_ENOUGH_INFO": { text: "Chưa đủ thông tin", color: "gray", icon: "?" }
  };

  const list = document.createElement("div");
  list.className = "vn-claim-verdicts-list";

  apiResponse.claim_verdicts.forEach((cv, index) => {
    const item = document.createElement("div");
    item.className = "vn-claim-verdict-item";

    const header = document.createElement("div");
    header.className = "vn-claim-header";

    const number = document.createElement("span");
    number.className = "vn-claim-number";
    number.innerText = `Luận điểm ${index + 1}:`;

    const badge = document.createElement("span");
    const info = verdictInfo[cv.verdict] || { text: cv.verdict, color: "gray", icon: "?" };
    badge.className = `vn-claim-verdict-badge ${info.color}`;
    badge.innerHTML = `${info.icon} ${info.text} (${Math.round(cv.confidence * 100)}%)`;

    header.appendChild(number);
    header.appendChild(badge);

    const claimText = document.createElement("p");
    claimText.className = "vn-claim-text";
    claimText.innerText = cv.claim_text;

    item.appendChild(header);
    item.appendChild(claimText);

    appendEvidenceSection(item, cv.supporting_evidence, "supporting", "📗 Bằng chứng hỗ trợ:");
    appendEvidenceSection(item, cv.refuting_evidence, "refuting", "📕 Bằng chứng bác bỏ:");

    list.appendChild(item);
  });

  return createCollapsibleSection("Phân tích chi tiết", list, true);
}

function appendEvidenceSection(parent, evidences, type, titleText) {
  if (!evidences || evidences.length === 0) return;

  const container = document.createElement("div");
  container.className = `vn-evidence-container ${type}`;

  const title = document.createElement("h5");
  title.className = "vn-evidence-title";
  title.innerText = titleText;
  container.appendChild(title);

  evidences.forEach(evidence => {
    const evidenceItem = document.createElement("div");
    evidenceItem.className = "vn-evidence-item";

    const articleHeader = document.createElement("div");
    articleHeader.className = "vn-evidence-article-header";

    const articleLink = document.createElement("a");
    articleLink.href = evidence.article_url || "#";
    articleLink.target = "_blank";
    articleLink.className = "vn-evidence-article-title";
    articleLink.innerText = evidence.article_title || "Bài báo";

    const articleMeta = document.createElement("span");
    articleMeta.className = "vn-evidence-source";
    articleMeta.innerText = `${evidence.source_name}${evidence.published_at ? ' - ' + new Date(evidence.published_at).toLocaleDateString('vi-VN') : ''}`;

    articleHeader.appendChild(articleLink);
    articleHeader.appendChild(articleMeta);
    evidenceItem.appendChild(articleHeader);

    if (evidence.overall_reasoning) {
      const reasoning = document.createElement("p");
      reasoning.className = "vn-evidence-reasoning";
      reasoning.innerText = evidence.overall_reasoning;
      evidenceItem.appendChild(reasoning);
    }

    if (evidence.evidence_spans && evidence.evidence_spans.length > 0) {
      const spansContainer = document.createElement("div");
      spansContainer.className = "vn-evidence-spans";

      evidence.evidence_spans.forEach((span) => {
        const spanItem = document.createElement("div");
        spanItem.className = "vn-evidence-span-item";

        const spanQuote = document.createElement("blockquote");
        spanQuote.className = "vn-evidence-quote";
        spanQuote.innerText = `"${span.text}"`;

        const spanReasoning = document.createElement("p");
        spanReasoning.className = "vn-span-reasoning";
        spanReasoning.innerText = `→ ${span.reasoning}`;

        spanItem.appendChild(spanQuote);
        spanItem.appendChild(spanReasoning);
        spansContainer.appendChild(spanItem);
      });

      evidenceItem.appendChild(spansContainer);
    }

    container.appendChild(evidenceItem);
  });

  parent.appendChild(container);
}

function createContentSection(content, createCollapsibleSection) {
  const contentDiv = document.createElement("div");
  contentDiv.className = "vn-article-content-text";
  const contentP = document.createElement("p");
  contentP.innerText = content;
  contentDiv.appendChild(contentP);
  return createCollapsibleSection("Nội dung bài đăng", contentDiv, true);
}

function createContextBanner(apiResponse) {
  if (!apiResponse.contextual_judgment || !apiResponse.contextual_judgment.is_out_of_context) return null;

  const container = document.createElement("div");
  container.className = "vn-context-banner";
  const title = document.createElement("h4");
  title.className = "vn-context-title";
  title.innerText = "⚠ Cảnh báo ngữ cảnh";
  const reasoning = document.createElement("p");
  reasoning.className = "vn-context-reasoning";
  reasoning.innerText = apiResponse.contextual_judgment.reasoning;
  container.appendChild(title);
  container.appendChild(reasoning);
  return container;
}

function createFooter({ apiResponse, content }) {
  const footer = document.createElement("div");
  footer.className = "vn-modal-footer";

  const footerLeft = document.createElement("div");
  footerLeft.className = "vn-footer-left";

  const footerInfo = document.createElement("div");
  footerInfo.className = "vn-footer-info";
  const timeSec = (apiResponse._veriNewsMetadata.total_time_ms / 1000).toFixed(2);
  footerInfo.innerHTML = `<span class="vn-footer-label">Thời gian:</span> ${timeSec}s`;

  const footerDisclaimer = document.createElement("div");
  footerDisclaimer.className = "vn-footer-disclaimer";
  footerDisclaimer.innerText = "⚡ Kết quả phân tích bởi AI chỉ mang tính tham khảo";

  footerLeft.appendChild(footerInfo);
  footerLeft.appendChild(footerDisclaimer);
  footer.appendChild(footerLeft);

  const refreshButton = document.createElement("button");
  refreshButton.className = "vn-refresh-button";
  refreshButton.innerHTML = `<span class="vn-refresh-icon">↻</span> Xác minh lại`;

  refreshButton.addEventListener("click", async () => {
    refreshButton.disabled = true;
    refreshButton.innerText = "Đang xác minh...";
    try {
      const progressTracker = createProgressTracker(
        (event) => console.log("Stage update:", event),
        (progress) => console.log("Progress:", progress),
        null,
        (error) => {
          console.error("Verification error:", error);
          refreshButton.disabled = false;
          refreshButton.innerText = "Thất bại - Thử lại";
        }
      );

      document.querySelector(".vn-modal-overlay")?.remove();
      showContentPopup(content, null, progressTracker, (response) => {
        document.querySelector(".vn-modal-overlay")?.remove();
        document.querySelector(".vn-modal-content")?.remove();
        showContentPopup(content, response);
        refreshButton.disabled = false;
        refreshButton.innerText = "Xác minh lại";
      });

      progressTracker.startStreaming(content, true);
    } catch (error) {
      console.error(error);
      refreshButton.disabled = false;
      refreshButton.innerText = "Thất bại - Thử lại";
    }
  });

  footer.appendChild(refreshButton);
  return footer;
}

/**
 * Creates and attaches an overlay and extract button to a target element.
 * @param {HTMLElement} target - The element to overlay.
 * @param {string} type - The type of content ('post', 'comment', 'complementary').
 */
async function createOverlay(target, type) {
  target.setAttribute(PROCESSED_ATTR, "true");
  let preliminaryText;
  if (type === "post") preliminaryText = getTextFromPost(target);
  else if (type === "comment") preliminaryText = getTextFromComment(target);
  else if (type === "complementary") preliminaryText = getTextFromComplementary(target);

  if (!preliminaryText || preliminaryText.trim() === "" || preliminaryText.startsWith("No text found")) return;

  const button = document.createElement("button");
  button.className = "vn-extract-button";
  const buttonImg = document.createElement("img");
  buttonImg.src = chrome.runtime.getURL("src/assets/images/verify_button.png");
  buttonImg.alt = "Xác minh";
  buttonImg.className = `vn-verify-image ${type}`;
  button.appendChild(buttonImg);

  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    buttonImg.alt = "Đang trích xuất...";
    button.disabled = true;
    showContentPopup("Đang trích xuất nội dung...", null);
    const extracted = await extractText(target, type);

    // Create progress tracker for streaming verification
    const progressTracker = createProgressTracker(
      (event) => console.log("Stage update:", event),
      (progress) => console.log("Progress:", progress),
      null, // onComplete will be handled by createProgressLoadingUI
      (error) => {
        // Don't remove modal overlay - let error UI display inside the modal
        console.error("Verification error:", error);
        buttonImg.alt = "Xác minh";
        button.disabled = false;
      }
    );

    // Show progress UI with completion handler
    document.querySelector(".vn-modal-overlay")?.remove();
    showContentPopup(extracted, null, progressTracker, (response) => {
      // Results received, remove progress modal and show results
      document.querySelector(".vn-modal-overlay")?.remove();
      document.querySelector(".vn-modal-content")?.remove();
      showContentPopup(extracted, response);
      buttonImg.alt = "Xác minh";
      button.disabled = false;
    });

    // Start streaming verification
    progressTracker.startStreaming(extracted, false);
  });

  const overlay = document.createElement("div");
  overlay.className = `vn-overlay ${type}`;
  overlay.appendChild(button);
  target.appendChild(overlay);
}
