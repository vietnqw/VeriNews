/**
 * Checks if an element is a comment.
 * @param {HTMLElement} element - The element to check.
 * @returns {boolean} True if the element is a comment.
 */
function isComment(element) {
  const ariaLabel = element.getAttribute("aria-label");
  if (
    ariaLabel &&
    (ariaLabel.toLowerCase().includes("comment") ||
      ariaLabel.toLowerCase().includes("reply"))
  ) {
    return true;
  }
  return !!element.parentElement?.closest('[role="article"]');
}

/**
 * Waits for an element to appear in a parent node.
 * @param {string} selector - The CSS selector for the element.
 * @param {HTMLElement} parent - The parent element to search within.
 * @param {number} timeout - The maximum time to wait in ms.
 * @returns {Promise<HTMLElement|null>} - A promise that resolves with the element or null if timed out.
 */
function waitForElement(selector, parent, timeout = 3000) {
  return new Promise((resolve) => {
    const intervalTime = 100;
    let elapsedTime = 0;

    const intervalId = setInterval(() => {
      const element = parent.querySelector(selector);
      if (element) {
        clearInterval(intervalId);
        resolve(element);
      } else {
        elapsedTime += intervalTime;
        if (elapsedTime >= timeout) {
          clearInterval(intervalId);
          resolve(null);
        }
      }
    }, intervalTime);
  });
}
