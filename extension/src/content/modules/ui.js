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
    svg.appendChild(createSvgElement("path", { d: "M9.5 14.5l-1.5 1.5a3 3 0 1 1-4.2-4.2l2.8-2.8" }));
    svg.appendChild(createSvgElement("path", { d: "M14.5 9.5l1.5-1.5a3 3 0 1 1 4.2 4.2l-2.8 2.8" }));
    svg.appendChild(createSvgElement("line", { x1: "9", y1: "15", x2: "15", y2: "9" }));
  },
  checklist: (svg) => {
    svg.appendChild(createSvgElement("rect", { x: "5", y: "5", width: "14", height: "14", rx: "2" }));
    svg.appendChild(createSvgElement("polyline", { points: "7 9.5 8.7 11.2 11.2 8.7" }));
    svg.appendChild(createSvgElement("line", { x1: "9", y1: "13", x2: "16", y2: "13" }));
    svg.appendChild(createSvgElement("line", { x1: "9", y1: "16.5", x2: "16", y2: "16.5" }));
    svg.appendChild(createSvgElement("circle", { cx: "7", cy: "16.5", r: "0.6", fill: "currentColor", stroke: "none" }));
  },
  analytics: (svg) => {
    svg.appendChild(createSvgElement("line", { x1: "6", y1: "18", x2: "6", y2: "12" }));
    svg.appendChild(createSvgElement("line", { x1: "12", y1: "18", x2: "12", y2: "8" }));
    svg.appendChild(createSvgElement("line", { x1: "18", y1: "18", x2: "18", y2: "5" }));
    svg.appendChild(createSvgElement("line", { x1: "4", y1: "18", x2: "20", y2: "18", "stroke-linecap": "butt" }));
  },
  article: (svg) => {
    svg.appendChild(createSvgElement("rect", { x: "6", y: "4.5", width: "12", height: "15", rx: "2" }));
    svg.appendChild(createSvgElement("line", { x1: "9", y1: "9", x2: "15", y2: "9" }));
    svg.appendChild(createSvgElement("line", { x1: "9", y1: "12", x2: "15", y2: "12" }));
    svg.appendChild(createSvgElement("line", { x1: "9", y1: "15", x2: "13", y2: "15" }));
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
 * Displays a modal popup with the extracted content.
 * @param {string} content - The text content to display.
 * @param {object | null} apiResponse - The response from the API, or null for loading state.
 * @param {object | null} progressTracker - Optional progress tracker for SSE updates.
 * @param {Function | null} onComplete - Callback when progress completes (for streaming mode).
 */
function showContentPopup(content, apiResponse, progressTracker = null, onComplete = null) {
  // --- Create Popup Elements ---
  const overlay = document.createElement("div");
  overlay.className = "vn-modal-overlay";

  const modal = document.createElement("div");
  modal.className = "vn-modal-content";

  const closeButton = document.createElement("button");
    closeButton.className = "vn-modal-close";
    modal.appendChild(closeButton);

    // Helper for JS-based Tooltip (Fixed positioning to escape overflow)
    let activeTooltip = null;

    function showTooltip(target, text) {
      if (activeTooltip) activeTooltip.remove();

      const tooltip = document.createElement("div");
      tooltip.className = "vn-floating-tooltip";
      // Allow basic HTML (e.g., <strong>) in tooltip content.
      // Content comes from static strings in the extension, not user input.
      tooltip.innerHTML = text;
      document.body.appendChild(tooltip);
      activeTooltip = tooltip;

      const rect = target.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();

      // Calculate position (centered above the element)
      let top = rect.top - tooltipRect.height - 10; // 10px gap
      let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);

      // Prevent going off-screen (left/right)
      if (left < 10) left = 10;
      if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
      }

      // Prevent going off-screen (top) -> flip to bottom if needed
      if (top < 10) {
         top = rect.bottom + 10;
         tooltip.classList.add("bottom");
      }

      tooltip.style.top = `${top}px`;
      tooltip.style.left = `${left}px`;

      // Trigger animation
      requestAnimationFrame(() => {
        tooltip.classList.add("visible");
      });
    }

    function hideTooltip() {
      if (activeTooltip) {
        activeTooltip.classList.remove("visible");
        const tooltipToRemove = activeTooltip;
        activeTooltip = null;
        setTimeout(() => {
          if (tooltipToRemove.parentNode) tooltipToRemove.remove();
        }, 200); // Wait for fade out
      }
    }

    // Helper function to create consistent collapsible sections
  function createCollapsibleSection(title, contentElement, isCollapsed = true) {
    const iconMap = {
      "Bài báo liên quan": "link",
      "Điểm chi tiết": "checklist",
      "Phân tích chi tiết": "analytics",
      "Nội dung bài đăng": "article"
    };

    const section = document.createElement("details");
    section.className = "vn-details-section";
    if (!isCollapsed) {
      section.setAttribute("open", "");
    }

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
  }

  if (!apiResponse) {
    // Loading state with progress tracking
    if (progressTracker) {
      // Use enhanced progress UI with stages
      const progressContainer = createProgressLoadingUI(progressTracker, onComplete);
      modal.appendChild(progressContainer);
    } else {
      // Fallback to simple spinner
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
  } else if (apiResponse.error) {
    // --- Error State ---
    const errorContainer = document.createElement("div");
    errorContainer.className = "vn-error-container";

    const errorTitle = document.createElement("h3");
    errorTitle.className = "vn-error-title";
    errorTitle.innerText = "Xác minh thất bại";

    const errorMessage = document.createElement("p");
    errorMessage.className = "vn-error-message";
    errorMessage.innerText = apiResponse.message;

    errorContainer.appendChild(errorTitle);
    errorContainer.appendChild(errorMessage);
    modal.appendChild(errorContainer);
  } else {
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
    modal.appendChild(heroSection);

    const sectionsContainer = document.createElement("div");
    sectionsContainer.className = "vn-result-body";

    const explanationSection = document.createElement("section");
    explanationSection.className = "vn-result-section";

    const explanationHeading = document.createElement("h2");
    explanationHeading.className = "vn-section-heading";
    explanationHeading.innerText = "Giải thích";

    const explanationText = document.createElement("p");
    explanationText.className = "vn-section-text";
    explanationText.innerText =
      apiResponse.explanation && apiResponse.explanation.trim() !== ""
        ? apiResponse.explanation
        : "Hệ thống chưa cung cấp giải thích chi tiết cho kết quả này.";

    explanationSection.appendChild(explanationHeading);
    explanationSection.appendChild(explanationText);
    sectionsContainer.appendChild(explanationSection);

    // --- Bài báo liên quan ---
    const articlesContainer = document.createElement("div");
    articlesContainer.className = "vn-articles-section";
    const hasArticles = apiResponse.matched_articles && apiResponse.matched_articles.length > 0;

    if (hasArticles) {
      const articlesList = document.createElement("div");
      articlesList.className = "vn-related-list";
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
        articlesList.appendChild(articleCard);
      });
      articlesContainer.appendChild(articlesList);
    } else {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "vn-empty-message";
      emptyMessage.innerText = "Không tìm thấy bài báo liên quan.";
      articlesContainer.appendChild(emptyMessage);
    }

    sectionsContainer.appendChild(createCollapsibleSection("Bài báo liên quan", articlesContainer, false));

    // --- Điểm chi tiết ---
    if (apiResponse.per_criterion_scores) {
      const scores = apiResponse.per_criterion_scores;
      const hasScores = scores.evidence_quality > 0 || scores.source_agreement > 0 ||
                       scores.source_quantity > 0 || scores.temporal_relevance > 0;

      if (hasScores) {
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
          const scoreRow = document.createElement("div");
          scoreRow.className = "vn-score-row";

          const scoreRowLabel = document.createElement("span");
          scoreRowLabel.className = "vn-score-row-label";
          scoreRowLabel.innerText = item.label;

          scoreRowLabel.addEventListener("mouseenter", () => showTooltip(scoreRowLabel, item.description));
          scoreRowLabel.addEventListener("mouseleave", hideTooltip);
          scoreRowLabel.addEventListener("click", (e) => {
             e.stopPropagation();
             showTooltip(scoreRowLabel, item.description);
          });

          const scoreRowValue = document.createElement("span");
          scoreRowValue.className = "vn-score-row-value";
          scoreRowValue.innerText = `${Math.round(item.value * 100)}%`;

          scoreRow.appendChild(scoreRowLabel);
          scoreRow.appendChild(scoreRowValue);
          criterionDetails.appendChild(scoreRow);
        });

        sectionsContainer.appendChild(createCollapsibleSection("Điểm chi tiết", criterionDetails, false));
      }
    }

    // --- Phân tích chi tiết ---
    if (apiResponse.claim_verdicts && apiResponse.claim_verdicts.length > 0) {
      const claimVerdictsList = document.createElement("div");
      claimVerdictsList.className = "vn-claim-verdicts-list";

      const verdictInfo = {
        "SUPPORTED": { text: "Được hỗ trợ", color: "green", icon: "✓" },
        "REFUTED": { text: "Bị bác bỏ", color: "red", icon: "✗" },
        "NOT_ENOUGH_INFO": { text: "Chưa đủ thông tin", color: "gray", icon: "?" }
      };

      apiResponse.claim_verdicts.forEach((cv, index) => {
        const claimItem = document.createElement("div");
        claimItem.className = "vn-claim-verdict-item";

        const claimHeader = document.createElement("div");
        claimHeader.className = "vn-claim-header";

        const claimNumber = document.createElement("span");
        claimNumber.className = "vn-claim-number";
        claimNumber.innerText = `Luận điểm ${index + 1}:`;

        const claimVerdictBadge = document.createElement("span");
        const info = verdictInfo[cv.verdict] || { text: cv.verdict, color: "gray", icon: "?" };
        claimVerdictBadge.className = `vn-claim-verdict-badge ${info.color}`;
        claimVerdictBadge.innerHTML = `${info.icon} ${info.text} (${Math.round(cv.confidence * 100)}%)`;

        claimHeader.appendChild(claimNumber);
        claimHeader.appendChild(claimVerdictBadge);

        const claimText = document.createElement("p");
        claimText.className = "vn-claim-text";
        claimText.innerText = cv.claim_text;

        claimItem.appendChild(claimHeader);
        claimItem.appendChild(claimText);

        if (cv.supporting_evidence && cv.supporting_evidence.length > 0) {
          const supportingContainer = document.createElement("div");
          supportingContainer.className = "vn-evidence-container supporting";
          const supportingTitle = document.createElement("h5");
          supportingTitle.className = "vn-evidence-title";
          supportingTitle.innerText = "📗 Bằng chứng hỗ trợ:";
          supportingContainer.appendChild(supportingTitle);
          cv.supporting_evidence.forEach(evidence => {
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

            supportingContainer.appendChild(evidenceItem);
          });
          claimItem.appendChild(supportingContainer);
        }

        if (cv.refuting_evidence && cv.refuting_evidence.length > 0) {
          const refutingContainer = document.createElement("div");
          refutingContainer.className = "vn-evidence-container refuting";
          const refutingTitle = document.createElement("h5");
          refutingTitle.className = "vn-evidence-title";
          refutingTitle.innerText = "📕 Bằng chứng bác bỏ:";
          refutingContainer.appendChild(refutingTitle);
          cv.refuting_evidence.forEach(evidence => {
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

            refutingContainer.appendChild(evidenceItem);
          });
          claimItem.appendChild(refutingContainer);
        }

        claimVerdictsList.appendChild(claimItem);
      });

      sectionsContainer.appendChild(createCollapsibleSection("Phân tích chi tiết", claimVerdictsList, true));
    }

    // --- Nội dung bài đăng ---
    const contentDiv = document.createElement("div");
    contentDiv.className = "vn-article-content-text";
    const contentP = document.createElement("p");
    contentP.innerText = content;
    contentDiv.appendChild(contentP);
    sectionsContainer.appendChild(createCollapsibleSection("Nội dung bài đăng", contentDiv, true));

    if (apiResponse.contextual_judgment && apiResponse.contextual_judgment.is_out_of_context) {
      const contextContainer = document.createElement("div");
      contextContainer.className = "vn-context-banner";
      const contextTitle = document.createElement("h4");
      contextTitle.className = "vn-context-title";
      contextTitle.innerText = "⚠ Cảnh báo ngữ cảnh";
      const contextReasoning = document.createElement("p");
      contextReasoning.className = "vn-context-reasoning";
      contextReasoning.innerText = apiResponse.contextual_judgment.reasoning;
      contextContainer.appendChild(contextTitle);
      contextContainer.appendChild(contextReasoning);
      sectionsContainer.appendChild(contextContainer);
    }

    modal.appendChild(sectionsContainer);
  }

  // --- Footer ---
  if (apiResponse && !apiResponse.error && apiResponse._veriNewsMetadata) {
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
        // Create progress tracker for streaming
        const progressTracker = createProgressTracker(
          (event) => console.log("Stage update:", event),
          (progress) => console.log("Progress:", progress),
          null, // onComplete will be handled by createProgressLoadingUI
          (error) => {
            // Don't remove modal overlay - let error UI display inside the modal
            console.error("Verification error:", error);
            refreshButton.disabled = false;
            refreshButton.innerText = "Thất bại - Thử lại";
          }
        );

        // Show progress UI with completion handler
        document.querySelector(".vn-modal-overlay")?.remove();
        showContentPopup(content, null, progressTracker, (response) => {
          // Results received, remove progress modal and show results
          document.querySelector(".vn-modal-overlay")?.remove();
          document.querySelector(".vn-modal-content")?.remove();
          showContentPopup(content, response);
          refreshButton.disabled = false;
          refreshButton.innerText = "Xác minh lại";
        });

        // Start streaming verification
        progressTracker.startStreaming(content, true);
      } catch (error) {
        console.error(error);
        refreshButton.disabled = false;
        refreshButton.innerText = "Thất bại - Thử lại";
      }
    });

    footer.appendChild(refreshButton);
    modal.appendChild(footer);
  }

  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  const closeModal = () => document.body.removeChild(overlay);
  closeButton.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
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
