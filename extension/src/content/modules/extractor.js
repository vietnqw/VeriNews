/**
 * Gets the text from a post element using a precise selector.
 * @param {HTMLElement} element - The post element.
 * @returns {string} The extracted text.
 */
function getTextFromPost(element) {
  let textContent = "";

  // STRATEGY 1: Use the precise 'message' container attribute. This is the best method.
  const messageSelector = '[data-ad-preview="message"], [data-ad-rendering-role="story_message"]';
  const messageContainer = element.matches(messageSelector)
    ? element
    : element.querySelector(messageSelector);

  if (messageContainer) {
    // Try div[dir="auto"] first (common structure)
    let textNodes = messageContainer.querySelectorAll('div[dir="auto"]');

    // If no div[dir="auto"], try span[dir="auto"] (alternative Facebook structure)
    if (textNodes.length === 0) {
      textNodes = messageContainer.querySelectorAll('span[dir="auto"]');
    }

    if (textNodes.length > 0) {
      textContent = Array.from(textNodes)
        .map((node) => node.innerText)
        .join("\n\n");
    } else {
      // Fallback: get all text directly from the message container
      textContent = messageContainer.innerText;
    }
  } else {
    // STRATEGY 2 (FALLBACK): If the specific container doesn't exist, use a safer version of the old logic.
    // Try div[dir="auto"] first
    let allTextNodes = element.querySelectorAll('div[dir="auto"]');

    // If no div[dir="auto"], try span[dir="auto"]
    if (allTextNodes.length === 0) {
      allTextNodes = element.querySelectorAll('span[dir="auto"]');
    }

    // Filter out any that are inside a nested 'article' (a comment).
    const postTextNodes = Array.from(allTextNodes).filter((node) => {
      // The closest article parent should be the element itself, not another one.
      return node.closest('[role="article"]') === element;
    });
    textContent = postTextNodes.map((node) => node.innerText).join("\n\n");
  }

  return textContent || "No text found.";
}

/**
 * Extracts the text content specifically from a comment element using a precise strategy.
 * @param {HTMLElement} element - The comment's [role="article"] element.
 * @returns {string} The extracted text.
 */
function getTextFromComment(element) {
  // --- STRATEGY 1: The most precise method ---
  // The main comment text is almost always in a div with this specific style.
  const specificContentNode = element.querySelector(
    'div[dir="auto"][style*="text-align: start"]'
  );
  if (specificContentNode && specificContentNode.innerText.trim()) {
    return specificContentNode.innerText.trim();
  }

  // Also try span variant
  const specificContentSpan = element.querySelector(
    'span[dir="auto"][style*="text-align: start"]'
  );
  if (specificContentSpan && specificContentSpan.innerText.trim()) {
    return specificContentSpan.innerText.trim();
  }

  // --- STRATEGY 2: Fallback for different structures ---
  // If the first method fails, find all text nodes and exclude the author's name.
  let allTextNodes = Array.from(element.querySelectorAll('div[dir="auto"]'));

  // If no div[dir="auto"], try span[dir="auto"]
  if (allTextNodes.length === 0) {
    allTextNodes = Array.from(element.querySelectorAll('span[dir="auto"]'));
  }

  const authorLink = element.querySelector(
    'a[href*="profile.php"], a[href*="?id="], a[href*="/user/"]'
  );

  // Find the specific node that contains the author link
  const authorNode = authorLink
    ? allTextNodes.find((node) => node.contains(authorLink))
    : null;

  // Find the first node that is NOT the author's node and has text.
  const contentNode = allTextNodes.find(
    (node) => node !== authorNode && node.innerText.trim()
  );

  if (contentNode) {
    return contentNode.innerText.trim();
  }

  return "No text found.";
}

/**
 * Extracts text specifically from a complementary view (Reel or Photo)
 * by trying multiple strategies.
 * @param {HTMLElement} element - The [role="complementary"] element.
 * @returns {string} The extracted text.
 */
function getTextFromComplementary(element) {
  // --- STRATEGY 1: Precise selector for Photo view ---
  const photoContentNode = element.querySelector("div.xyinxu5");
  if (photoContentNode && photoContentNode.innerText.trim()) {
    return photoContentNode.innerText.trim();
  }

  // --- STRATEGY 2: Fallback selector for Reel view ---
  // The main text is often the first non-empty span with dir="auto"
  // that is NOT inside a comment.
  const textSpans = element.querySelectorAll('span[dir="auto"]');
  for (const span of textSpans) {
    // Ensure the span is not part of a comment nested within the complementary view
    if (!span.closest('[role="article"]')) {
      const text = span.innerText.trim();
      if (text) {
        // Return the first valid, non-empty text found
        return text;
      }
    }
  }

  return "No text found in complementary view.";
}

/**
 * Asynchronously extracts the full text content from a detected element,
 * handling the "See more" button if it exists.
 * @param {HTMLElement} target - The element to extract text from.
 * @param {string} type - The type of content ('post', 'comment', 'complementary').
 * @returns {Promise<string>} - A promise that resolves with the extracted text.
 */
async function extractText(target, type) {
  let getTextFunction;

  // Route to the correct helper function based on the content type.
  if (type === "post") {
    getTextFunction = getTextFromPost;
  } else if (type === "comment") {
    getTextFunction = getTextFromComment;
  } else if (type === "complementary") {
    getTextFunction = getTextFromComplementary;
  } else {
    return Promise.resolve("Extraction not supported for this type.");
  }

  const seeMoreButton = Array.from(
    target.querySelectorAll('div[role="button"]')
  ).find((el) => el.innerText.toLowerCase() === "see more");

  if (!seeMoreButton) {
    // If no "See more", get text immediately.
    return Promise.resolve(getTextFunction(target));
  } else {
    // If "See more" exists, click it and wait.
    return new Promise((resolve) => {
      const observer = new MutationObserver((_mutations, obs) => {
        obs.disconnect();
        resolve(getTextFunction(target));
      });
      observer.observe(target, { childList: true, subtree: true });
      seeMoreButton.click();
    });
  }
}
