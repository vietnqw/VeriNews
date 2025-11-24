let observer = null;

/**
 * Finds and processes all detectable content types within a given node.
 */
function findAndProcessContent(node) {
  if (node.nodeType !== Node.ELEMENT_NODE) return;

  // --- 1. Process standard Posts and Comments ---
  const articles = node.querySelectorAll(
    `[role="article"]:not([${PROCESSED_ATTR}])`
  );

  articles.forEach((article) => {
    if (isComment(article)) {
      createOverlay(article, "comment");
    } else {
      createOverlay(article, "post");
    }
  });

  // --- 2. Process Complementary Posts (ONLY on relevant pages) ---
  const currentPath = window.location.pathname;
  if (currentPath.includes("/reel/") || currentPath.includes("/photo/")) {
    const complementaryPosts = node.querySelectorAll(
      `[role="complementary"]:not([${PROCESSED_ATTR}])`
    );
    complementaryPosts.forEach((post) => {
      createOverlay(post, "complementary");
    });
  }

  // --- 3. Fallback: Detect posts missing role="article" (e.g., platform variants) ---
  const messageNodes = node.querySelectorAll(
    '[data-ad-preview="message"], [data-ad-rendering-role="story_message"]'
  );

  messageNodes.forEach((message) => {
    const postRoot =
      message.closest('[role="article"], div[aria-labelledby][aria-describedby]') ||
      message.parentElement ||
      message;

    // Skip if already processed
    if (postRoot.hasAttribute(PROCESSED_ATTR)) return;

    // Skip if inside complementary (handled above)
    if (postRoot.closest('[role="complementary"]')) return;

    // If there's a nearest role=article wrapper and it's a comment, skip
    const nearestArticle = message.closest('[role="article"]');
    if (nearestArticle && isComment(nearestArticle)) return;

    createOverlay(postRoot, "post");
  });
}

function startObserver() {
  console.log("✅ Extension is ON. Starting to observe...");
  if (observer) return;

  findAndProcessContent(document.body);

  observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        findAndProcessContent(node);
      });
      if (mutation.type === "attributes") {
        findAndProcessContent(mutation.target);
      }
    });
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
  });

  // Store the new, active observer on a global variable so we can disconnect it on reload.
  window.verinewsObserver = observer;
}

function stopObserver() {
  console.log("❌ Extension is OFF. Stopping operations...");
  if (observer) {
    observer.disconnect();
    observer = null;
  }
  window.verinewsObserver = null;

  // Clean up by removing all injected elements
  document
    .querySelectorAll(
      ".vn-overlay, .vn-extract-button, .vn-modal-overlay, .vn-menu-button"
    )
    .forEach((el) => el.remove());
  document
    .querySelectorAll(`[${PROCESSED_ATTR}]`)
    .forEach((el) => el.removeAttribute(PROCESSED_ATTR));
}
