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
  closeButton.innerHTML = "&times;"; // The 'X' symbol
  modal.appendChild(closeButton);

  if (!apiResponse) {
    // Loading state
    const statusMessage = document.createElement("p");
    statusMessage.className = "vn-status-message";
    statusMessage.innerText = "Đang xác minh nội dung...";
    modal.appendChild(statusMessage);
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
    // --- Overall Decision & Score Section ---
    const decisionContainer = document.createElement("div");
    decisionContainer.className = "vn-decision-container";

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
      "Verified": "Đã xác minh",
      "Misleading/False": "Sai lệch/Giả mạo",
      "Out of Context": "Sai ngữ cảnh",
      "Unverified": "Chưa xác minh"
    };
    decisionText.innerText = decisionMap[apiResponse.overall_decision] || "Không rõ";

    decisionBadge.appendChild(decisionIcon);
    decisionBadge.appendChild(decisionText);

    // Score Display
    const scoreContainer = document.createElement("div");
    scoreContainer.className = "vn-score-container";
    const scoreValue = document.createElement("span");
    scoreValue.className = `vn-score-value ${apiResponse.flag}`;
    scoreValue.innerText = `${Math.round(apiResponse.final_score * 100)}%`;
    const scoreLabel = document.createElement("span");
    scoreLabel.className = "vn-score-label";
    scoreLabel.innerText = "Độ tin cậy";
    scoreContainer.appendChild(scoreValue);
    scoreContainer.appendChild(scoreLabel);

    decisionContainer.appendChild(decisionBadge);
    decisionContainer.appendChild(scoreContainer);
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
      const hasScores = scores.content_similarity > 0 || scores.support_ratio > 0 ||
                       scores.contradiction_ratio > 0 || scores.not_mentioned_ratio > 0;

      if (hasScores) {
        const criterionContainer = document.createElement("div");
        criterionContainer.className = "vn-criterion-container";

        const criterionToggle = document.createElement("button");
        criterionToggle.className = "vn-criterion-toggle";
        criterionToggle.innerText = "Hiển thị điểm chi tiết";

        const criterionDetails = document.createElement("div");
        criterionDetails.className = "vn-criterion-details collapsed";

        const scoreItems = [
          { label: "Độ liên quan chủ đề", value: scores.content_similarity, description: "Mức độ tương đồng giữa bài đăng và các bài báo" },
          { label: "Luận điểm được hỗ trợ", value: scores.support_ratio, description: "Tỷ lệ luận điểm được xác minh bằng bằng chứng" },
          { label: "Luận điểm bị mâu thuẫn", value: scores.contradiction_ratio, description: "Tỷ lệ luận điểm bị mâu thuẫn với bằng chứng" },
          { label: "Luận điểm không tìm thấy", value: scores.not_mentioned_ratio, description: "Tỷ lệ luận điểm không được đề cập trong bài báo" }
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
    const articlesTitle = document.createElement("h3");
    articlesTitle.className = "vn-articles-title";
    articlesTitle.innerText = "Bài báo liên quan";
    modal.appendChild(articlesTitle);

    const hasArticles =
      apiResponse.matched_articles && apiResponse.matched_articles.length > 0;

    if (hasArticles) {
      const articlesList = document.createElement("ul");
      articlesList.className = "vn-articles-list";
      apiResponse.matched_articles.forEach((article) => {
        const listItem = document.createElement("li");
        const link = document.createElement("a");
        link.href = article.url;
        link.target = "_blank";
        link.innerText = article.title; // Display the title

        const sourceSpan = document.createElement("span");
        sourceSpan.className = "vn-article-source";
        sourceSpan.innerText = ` - ${article.source} (${(
          article.similarity * 100
        ).toFixed(0)}%)`;

        listItem.appendChild(link);
        listItem.appendChild(sourceSpan);
        articlesList.appendChild(listItem);
      });
      modal.appendChild(articlesList);
    } else {
      const emptyMessage = document.createElement("p");
      emptyMessage.className = "vn-status-message";
      emptyMessage.innerText = "Không tìm thấy bài báo liên quan.";
      modal.appendChild(emptyMessage);
    }

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
  buttonImg.alt = "Verify";
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

    buttonImg.alt = "Verify";
    button.disabled = false;
  });

  // --- Placement Logic ---
  const overlay = document.createElement("div");
  overlay.className = `vn-overlay ${type}`;
  overlay.appendChild(button);
  target.appendChild(overlay);
}
