/**
 * Displays a modal popup with the extracted content.
 * @param {string} content - The text content to display.
 * @param {object | null} apiResponse - The response from the API, or null for loading state.
 */
function showContentPopup(content, apiResponse) {
  // --- Create Popup Elements ---
  const overlay = document.createElement("div");
  overlay.className = "vn-modal-overlay";

  const modal = document.createElement("div");
  modal.className = "vn-modal-content";

  const closeButton = document.createElement("button");
  closeButton.className = "vn-modal-close";
  modal.appendChild(closeButton);

  if (!apiResponse) {
    // Loading state with improved spinner and messaging
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
    // --- Overall Decision & Score Section (New Horizontal Layout) ---
    const decisionContainer = document.createElement("div");
    decisionContainer.className = "vn-decision-container";

    // Circular Score Display - Simple border style
    const scoreCircle = document.createElement("div");
    scoreCircle.className = `vn-score-circle ${apiResponse.flag}`;

    const scorePercent = Math.round(apiResponse.final_score * 100);

    const scoreValue = document.createElement("span");
    scoreValue.className = `vn-score-value ${apiResponse.flag}`;
    scoreValue.innerText = `${scorePercent}%`;

    const scoreLabel = document.createElement("span");
    scoreLabel.className = "vn-score-label";
    scoreLabel.innerText = "Độ tin cậy";

    scoreCircle.appendChild(scoreValue);
    scoreCircle.appendChild(scoreLabel);

    // Decision Info (badge + explanation)
    const decisionInfo = document.createElement("div");
    decisionInfo.className = "vn-decision-info";

    // Decision Badge
    const decisionBadge = document.createElement("div");
    decisionBadge.className = `vn-decision-badge ${apiResponse.flag}`;

    const decisionIcon = document.createElement("span");
    decisionIcon.className = "vn-decision-icon";
    // Map decisions to emoji icons
    const iconMap = {
      "green": "✓",
      "red": "✗",
      "yellow": "⚠",
      "gray": "?"
    };
    decisionIcon.innerText = iconMap[apiResponse.flag] || "?";

    const decisionText = document.createElement("span");
    decisionText.className = "vn-decision-text";
    // Map English decisions to Vietnamese
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
    decisionText.innerText = decisionMap[apiResponse.overall_decision] || "Không rõ";

    decisionBadge.appendChild(decisionIcon);
    decisionBadge.appendChild(decisionText);
    decisionInfo.appendChild(decisionBadge);

    // Add explanation inline if available
    if (apiResponse.explanation && apiResponse.explanation.trim() !== "") {
      const explanationText = document.createElement("p");
      explanationText.className = "vn-explanation-inline";
      explanationText.innerText = apiResponse.explanation;
      decisionInfo.appendChild(explanationText);
    }

    decisionContainer.appendChild(scoreCircle);
    decisionContainer.appendChild(decisionInfo);
    modal.appendChild(decisionContainer);

    // Add note about pending verification if Unverified
    if (apiResponse.overall_decision === "Unverified") {
      const noteContainer = document.createElement("div");
      noteContainer.className = "vn-info-note";
      noteContainer.innerHTML = "ℹ️ Chức năng xác minh đầy đủ sẽ được cập nhật sớm. Hiện tại chỉ hiển thị các bài báo liên quan.";
      modal.appendChild(noteContainer);
    }

    // --- Per-Criterion Scores (Collapsible) ---
    // Hide this section if scores are not available (all zeros)
    if (apiResponse.per_criterion_scores) {
      const scores = apiResponse.per_criterion_scores;
      const hasScores = scores.evidence_quality > 0 || scores.source_agreement > 0 ||
                       scores.claim_coverage > 0 || scores.stance_confidence > 0 ||
                       scores.temporal_relevance > 0;

      if (hasScores) {
        const criterionContainer = document.createElement("div");
        criterionContainer.className = "vn-criterion-container";

        const criterionToggle = document.createElement("button");
        criterionToggle.className = "vn-criterion-toggle";
        criterionToggle.innerText = "Hiển thị điểm chi tiết";

        const criterionDetails = document.createElement("div");
        criterionDetails.className = "vn-criterion-details collapsed";

        const scoreItems = [
          { label: "Chất lượng bằng chứng", value: scores.evidence_quality, description: "Mức độ liên quan của bằng chứng từ bài báo" },
          { label: "Độ đồng thuận nguồn", value: scores.source_agreement, description: "Tỷ lệ nguồn tin đồng ý về kết quả" },
          { label: "Độ phủ tuyên bố", value: scores.claim_coverage, description: "Tỷ lệ tuyên bố được xác minh đầy đủ" },
          { label: "Độ tin cậy phân loại", value: scores.stance_confidence, description: "Độ tin cậy của LLM trong việc phân loại lập trường" },
          { label: "Độ mới của bài báo", value: scores.temporal_relevance, description: "Mức độ cập nhật của các bài báo nguồn" }
        ];

        scoreItems.forEach(item => {
          const scoreRow = document.createElement("div");
          scoreRow.className = "vn-score-row";

          const scoreRowLabel = document.createElement("span");
          scoreRowLabel.className = "vn-score-row-label";
          scoreRowLabel.innerText = item.label;
          scoreRowLabel.title = item.description;

          const scoreRowValue = document.createElement("span");
          scoreRowValue.className = "vn-score-row-value";
          scoreRowValue.innerText = `${Math.round(item.value * 100)}%`;

          scoreRow.appendChild(scoreRowLabel);
          scoreRow.appendChild(scoreRowValue);
          criterionDetails.appendChild(scoreRow);
        });

        criterionToggle.addEventListener("click", () => {
          criterionDetails.classList.toggle("collapsed");
          criterionToggle.innerText = criterionDetails.classList.contains("collapsed")
            ? "Hiển thị điểm chi tiết"
            : "Ẩn điểm chi tiết";
        });

        criterionContainer.appendChild(criterionToggle);
        criterionContainer.appendChild(criterionDetails);
        modal.appendChild(criterionContainer);
      }
    }

    // --- Claim Verdicts Section (Collapsible) ---
    if (apiResponse.claim_verdicts && apiResponse.claim_verdicts.length > 0) {
      const claimVerdictsContainer = document.createElement("div");
      claimVerdictsContainer.className = "vn-claim-verdicts-container";

      const claimVerdictsToggle = document.createElement("button");
      claimVerdictsToggle.className = "vn-claim-verdicts-toggle";
      claimVerdictsToggle.innerText = "Hiển thị kết quả từng tuyên bố";

      const claimVerdictsList = document.createElement("div");
      claimVerdictsList.className = "vn-claim-verdicts-list collapsed";

      // Map verdict to Vietnamese and color
      const verdictInfo = {
        "SUPPORTED": { text: "Được hỗ trợ", color: "green", icon: "✓" },
        "REFUTED": { text: "Bị bác bỏ", color: "red", icon: "✗" },
        "NOT_ENOUGH_INFO": { text: "Chưa đủ thông tin", color: "gray", icon: "?" }
      };

      apiResponse.claim_verdicts.forEach((cv, index) => {
        const claimItem = document.createElement("div");
        claimItem.className = "vn-claim-verdict-item";

        // Claim header with verdict badge
        const claimHeader = document.createElement("div");
        claimHeader.className = "vn-claim-header";

        const claimNumber = document.createElement("span");
        claimNumber.className = "vn-claim-number";
        claimNumber.innerText = `Tuyên bố ${index + 1}:`;

        const claimVerdictBadge = document.createElement("span");
        const info = verdictInfo[cv.verdict] || { text: cv.verdict, color: "gray", icon: "?" };
        claimVerdictBadge.className = `vn-claim-verdict-badge ${info.color}`;
        claimVerdictBadge.innerHTML = `${info.icon} ${info.text} (${Math.round(cv.confidence * 100)}%)`;

        claimHeader.appendChild(claimNumber);
        claimHeader.appendChild(claimVerdictBadge);

        // Claim text
        const claimText = document.createElement("p");
        claimText.className = "vn-claim-text";
        claimText.innerText = cv.claim_text;

        claimItem.appendChild(claimHeader);
        claimItem.appendChild(claimText);

        // Supporting evidence
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

            const evidenceQuote = document.createElement("p");
            evidenceQuote.className = "vn-evidence-quote";
            evidenceQuote.innerText = `"${evidence.key_quote}"`;

            const evidenceSource = document.createElement("span");
            evidenceSource.className = "vn-evidence-source";
            evidenceSource.innerText = `— ${evidence.source_name}`;

            const evidenceReasoning = document.createElement("p");
            evidenceReasoning.className = "vn-evidence-reasoning";
            evidenceReasoning.innerText = evidence.reasoning;

            evidenceItem.appendChild(evidenceQuote);
            evidenceItem.appendChild(evidenceSource);
            evidenceItem.appendChild(evidenceReasoning);
            supportingContainer.appendChild(evidenceItem);
          });

          claimItem.appendChild(supportingContainer);
        }

        // Refuting evidence
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

            const evidenceQuote = document.createElement("p");
            evidenceQuote.className = "vn-evidence-quote";
            evidenceQuote.innerText = `"${evidence.key_quote}"`;

            const evidenceSource = document.createElement("span");
            evidenceSource.className = "vn-evidence-source";
            evidenceSource.innerText = `— ${evidence.source_name}`;

            const evidenceReasoning = document.createElement("p");
            evidenceReasoning.className = "vn-evidence-reasoning";
            evidenceReasoning.innerText = evidence.reasoning;

            evidenceItem.appendChild(evidenceQuote);
            evidenceItem.appendChild(evidenceSource);
            evidenceItem.appendChild(evidenceReasoning);
            refutingContainer.appendChild(evidenceItem);
          });

          claimItem.appendChild(refutingContainer);
        }

        claimVerdictsList.appendChild(claimItem);
      });

      claimVerdictsToggle.addEventListener("click", () => {
        claimVerdictsList.classList.toggle("collapsed");
        claimVerdictsToggle.innerText = claimVerdictsList.classList.contains("collapsed")
          ? "Hiển thị kết quả từng tuyên bố"
          : "Ẩn kết quả từng tuyên bố";
      });

      claimVerdictsContainer.appendChild(claimVerdictsToggle);
      claimVerdictsContainer.appendChild(claimVerdictsList);
      modal.appendChild(claimVerdictsContainer);
    }

    // --- Sources Used Section ---
    if (apiResponse.sources_used && apiResponse.sources_used.length > 0) {
      const sourcesContainer = document.createElement("div");
      sourcesContainer.className = "vn-sources-container";

      const sourcesTitle = document.createElement("h4");
      sourcesTitle.className = "vn-sources-title";
      sourcesTitle.innerText = "Nguồn tin sử dụng:";

      const sourcesList = document.createElement("span");
      sourcesList.className = "vn-sources-list";
      sourcesList.innerText = apiResponse.sources_used.join(", ");

      sourcesContainer.appendChild(sourcesTitle);
      sourcesContainer.appendChild(sourcesList);
      modal.appendChild(sourcesContainer);
    }

    // --- Contextual Judgment (if available) ---
    if (apiResponse.contextual_judgment && apiResponse.contextual_judgment.is_out_of_context) {
      const contextContainer = document.createElement("div");
      contextContainer.className = "vn-context-warning";

      const contextTitle = document.createElement("h4");
      contextTitle.className = "vn-context-title";
      contextTitle.innerText = "⚠ Cảnh báo ngữ cảnh";

      const contextReasoning = document.createElement("p");
      contextReasoning.className = "vn-context-reasoning";
      contextReasoning.innerText = apiResponse.contextual_judgment.reasoning;

      contextContainer.appendChild(contextTitle);
      contextContainer.appendChild(contextReasoning);
      modal.appendChild(contextContainer);
    }

    // --- Matched Articles Section ---
    const articlesSection = document.createElement("div");
    articlesSection.className = "vn-articles-section";

    const articlesTitle = document.createElement("h3");
    articlesTitle.className = "vn-articles-title";
    articlesTitle.innerText = "Bài Viết Liên Quan";
    articlesSection.appendChild(articlesTitle);

    const hasArticles =
      apiResponse.matched_articles && apiResponse.matched_articles.length > 0;

    if (hasArticles) {
      const articlesList = document.createElement("ul");
      articlesList.className = "vn-articles-list";
      apiResponse.matched_articles.forEach((article) => {
        const listItem = document.createElement("li");

        // Content wrapper
        const content = document.createElement("div");
        content.className = "vn-article-content";

        const link = document.createElement("a");
        link.href = article.url;
        link.target = "_blank";
        link.className = "vn-article-link";
        link.innerText = article.title;

        const meta = document.createElement("div");
        meta.className = "vn-article-meta";

        const sourceSpan = document.createElement("span");
        sourceSpan.className = "vn-article-source";
        sourceSpan.innerText = article.source;

        const separator = document.createElement("span");
        separator.innerText = " - ";

        const accuracySpan = document.createElement("span");
        const accuracy = Math.round(article.similarity * 100);
        // Determine color based on accuracy
        let accuracyColor = "gray";
        if (accuracy >= 80) accuracyColor = "green";
        else if (accuracy >= 50) accuracyColor = "yellow";
        else if (accuracy > 0) accuracyColor = "red";
        accuracySpan.className = `vn-article-accuracy ${accuracyColor}`;
        accuracySpan.innerText = `Mức độ liên quan ${accuracy}%`;

        meta.appendChild(sourceSpan);
        meta.appendChild(separator);
        meta.appendChild(accuracySpan);

        content.appendChild(link);
        content.appendChild(meta);

        const arrow = document.createElement("span");
        arrow.className = "vn-article-arrow";
        arrow.innerText = "›";

        listItem.appendChild(content);
        listItem.appendChild(arrow);
        articlesList.appendChild(listItem);
      });
      articlesSection.appendChild(articlesList);
    } else {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "vn-empty-message";
      emptyMessage.innerText = "Không tìm thấy bài báo liên quan.";
      articlesSection.appendChild(emptyMessage);
    }

    modal.appendChild(articlesSection);

    // --- Extracted Claims Section (Collapsible) ---
    // Only show if claims exist
    if (apiResponse.claims && apiResponse.claims.length > 0) {
      const claimsContainer = document.createElement("div");
      claimsContainer.className = "vn-claims-container";
      const claimsToggle = document.createElement("button");
      claimsToggle.className = "vn-claims-toggle";
      claimsToggle.innerText = "Hiển thị luận điểm trích xuất";
      const claimsList = document.createElement("ul");
      claimsList.className = "vn-claims-list collapsed";

      apiResponse.claims.forEach((claim) => {
        const listItem = document.createElement("li");
        listItem.innerText = claim;
        claimsList.appendChild(listItem);
      });

      claimsToggle.addEventListener("click", () => {
        claimsList.classList.toggle("collapsed");
        claimsToggle.innerText = claimsList.classList.contains("collapsed")
          ? "Hiển thị luận điểm trích xuất"
          : "Ẩn luận điểm trích xuất";
      });

      claimsContainer.appendChild(claimsToggle);
      claimsContainer.appendChild(claimsList);
      modal.appendChild(claimsContainer);
    }

    // --- Extracted Content Section (Collapsible) ---
    const contentContainer = document.createElement("div");
    contentContainer.className = "vn-content-container";
    const contentToggle = document.createElement("button");
    contentToggle.className = "vn-content-toggle";
    contentToggle.innerText = "Hiển thị nội dung gốc";
    const contentParagraph = document.createElement("p");
    contentParagraph.className = "vn-content-paragraph collapsed";
    contentParagraph.innerText = content;

    contentToggle.addEventListener("click", () => {
      contentParagraph.classList.toggle("collapsed");
      contentToggle.innerText = contentParagraph.classList.contains("collapsed")
        ? "Hiển thị nội dung gốc"
        : "Ẩn nội dung gốc";
    });

    contentContainer.appendChild(contentToggle);
    contentContainer.appendChild(contentParagraph);
    modal.appendChild(contentContainer);
  }
    // --- Modal Footer (only show after verification is complete) ---
    if (apiResponse && !apiResponse.error && apiResponse._veriNewsMetadata) {
      const footer = document.createElement("div");
      footer.className = "vn-modal-footer";

      // Add footer info (time)
      const footerInfo = document.createElement("div");
      footerInfo.className = "vn-footer-info";

      const timeMs = apiResponse._veriNewsMetadata.total_time_ms;
      const timeSec = (timeMs / 1000).toFixed(2);

      footerInfo.innerHTML = `<strong>Thời gian:</strong> ${timeSec} giây`;
      footer.appendChild(footerInfo);

      // Add refresh button for re-verification
      const refreshButton = document.createElement("button");
      refreshButton.className = "vn-refresh-button";
      refreshButton.innerHTML = `<span class="vn-refresh-icon">↻</span> Xác minh lại`;
      refreshButton.title = "Bỏ qua cache và xác minh lại";

      refreshButton.addEventListener("click", async () => {
        refreshButton.disabled = true;
        refreshButton.innerText = "Đang xác minh...";

        try {
          // callVerifyAPI is already available globally (loaded via manifest)
          // Call API with cache_bypass = true
          const newApiResponse = await callVerifyAPI(content, true);

          // Close current modal
          const existingOverlay = document.querySelector(".vn-modal-overlay");
          if (existingOverlay) {
            existingOverlay.remove();
          }

          // Show updated popup with new data
          showContentPopup(content, newApiResponse);
        } catch (error) {
          console.error("Error during re-verification:", error);
          refreshButton.disabled = false;
          refreshButton.innerText = "Thất bại - Thử lại";
        }
      });

      footer.appendChild(refreshButton);
      modal.appendChild(footer);
    }

  // --- Assemble the Popup ---
  overlay.appendChild(modal);

  // --- Add to Page ---
  document.body.appendChild(overlay);

  // --- Add Close Logic ---
  const closeModal = () => {
    document.body.removeChild(overlay);
  };

  closeButton.addEventListener("click", closeModal);

  // Optional: Allow clicking the dark background to close the modal too
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) {
      // Only if the click is on the overlay itself
      closeModal();
    }
  });
}

/**
 * Creates and attaches an overlay and extract button to a target element.
 * @param {HTMLElement} target - The element to overlay.
 * @param {string} type - The type of content ('post', 'comment', 'complementary').
 */
async function createOverlay(target, type) {
  target.setAttribute(PROCESSED_ATTR, "true");

  // --- PRE-CHECK FOR CONTENT ---
  // Before adding a button, do a quick check to see if there's any text content.
  let preliminaryText;
  if (type === "post") {
    preliminaryText = getTextFromPost(target);
  } else if (type === "comment") {
    preliminaryText = getTextFromComment(target);
  } else if (type === "complementary") {
    preliminaryText = getTextFromComplementary(target);
  }

  // If no valid text is found (empty, whitespace, or our "not found" message),
  // then don't add the button at all.
  if (
    !preliminaryText ||
    preliminaryText.trim() === "" ||
    preliminaryText.startsWith("No text found")
  ) {
    return;
  }

  // --- Button Creation (same for all types) ---
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

    // Show loading popup immediately
    showContentPopup("Đang trích xuất nội dung...", null);

    const extracted = await extractText(target, type);

    // Call API
    const apiResponse = await callVerifyAPI(extracted);

    // Close the old loading popup and show the new one with data
    const existingOverlay = document.querySelector(".vn-modal-overlay");
    if (existingOverlay) {
      existingOverlay.remove();
    }
    showContentPopup(extracted, apiResponse);

    buttonImg.alt = "Xác minh";
    button.disabled = false;
  });

  // --- Placement Logic ---
  const overlay = document.createElement("div");
  overlay.className = `vn-overlay ${type}`;
  overlay.appendChild(button);
  target.appendChild(overlay);
}
