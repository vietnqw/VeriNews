# VeriNews Browser Extension

Chrome extension for verifying credibility of Facebook posts using VeriNews AI-powered verification system.

## Features

- 🔍 **One-Click Verification**: Adds "Verify" button to Facebook posts and comments
- 📰 **Related Articles**: Shows matched news articles from trusted sources
- ⚡ **Real-time Analysis**: Semantic search with hybrid retrieval (vector + BM25)
- 🎯 **Smart Extraction**: Handles posts, comments, Reels, and Photo content
- 🇻🇳 **Vietnamese Optimized**: Built for Vietnamese language content

## Installation

### Development Mode

1. **Ensure Backend is Running**
   ```bash
   cd VeriNews/backend
   ./scripts/verinews dev start
   ./scripts/verinews crawler start
   ```

2. **Load Extension in Chrome**
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top-right)
   - Click "Load unpacked"
   - Select the `VeriNews/extension` directory
   - Extension icon should appear in toolbar

3. **Verify Connection**
   - Click extension icon in toolbar
   - Should show "Connected" with green indicator
   - If "Disconnected", check backend is running on `localhost:8000`

### Configuration

Edit `src/config/config.js` to change backend URL:

```javascript
BACKEND_BASE_URL: "http://localhost:8000",  // Development
// BACKEND_BASE_URL: "https://your-production-url.com",  // Production
```

## Usage

1. **Navigate to Facebook**
   - Go to any Facebook page with posts or comments
   - Extension auto-detects verifiable content

2. **Verify Content**
   - Look for the VeriNews verify button overlay on posts
   - Click the button to start verification
   - Modal popup shows loading state while processing

3. **Review Results**
   - **Status**: Currently shows "Unverified" (full verification pending)
   - **Related Articles**: List of matched news articles with similarity scores
   - **Original Content**: View extracted text (collapsible)
   - **Claims**: Extracted claims (when available)

4. **Toggle Extension**
   - Click extension icon to open popup
   - Use toggle switch to enable/disable verification buttons
   - State persists across browser sessions

## Project Structure

```
extension/
├── manifest.json              # Extension manifest (MV3)
├── src/
│   ├── assets/
│   │   ├── icons/            # Extension icons (16-128px)
│   │   └── images/           # Verify button image
│   ├── background/
│   │   └── service_worker.js # Health check monitoring
│   ├── config/
│   │   └── config.js         # Backend URL and settings
│   ├── content/
│   │   ├── content.js        # Main content script
│   │   └── modules/
│   │       ├── api.js        # API calls + response adapter
│   │       ├── constants.js  # Facebook selectors
│   │       ├── extractor.js  # Content extraction logic
│   │       ├── observer.js   # MutationObserver
│   │       ├── ui.js         # Modal UI generation
│   │       └── utils.js      # Helper functions
│   ├── popup/
│   │   ├── popup.html        # Extension popup UI
│   │   └── popup.js          # Popup logic
│   └── styles/
│       ├── popup.css         # Popup styles
│       └── styles.css        # Content injection styles
└── README.md
```

## API Integration

### Request Format

Extension sends text content to VeriNews API:

```javascript
POST /api/v1/verify
{
  "text": "Facebook post content..."
}
```

### Response Adapter

The extension includes an adapter layer (`api.js`) that transforms VeriNews API responses to work with the UI:

- **Normalizes scores**: Converts summed relevance scores to 0-1 similarity range
- **Handles missing fields**: Provides defaults for `claims`, `verdict`, `contextual_judgment`
- **Maps article data**: Transforms VeriNews article schema to MVP format
- **Fallback URLs**: Uses `article_id` when `url` field is unavailable

### Current Limitations

The following features are **not yet available** in VeriNews backend:

1. ❌ **Full Verification Verdict**: Always shows "Unverified" status
   - Backend returns `verdict: "NOT_IMPLEMENTED"`
   - Per-criterion scores (support ratio, contradiction ratio) not available
   - Contextual judgment (out-of-context detection) not implemented

2. ❌ **Claims in Response**: Claims extracted during processing but not returned
   - Claims section in UI remains empty
   - Backend stores claims in database but doesn't include in API response

3. ❌ **Article URLs**: Articles missing direct URLs to original sources
   - Uses `article_id` as fallback in links
   - Users cannot navigate to original articles

### Planned Backend Improvements

These changes will be implemented in a future task:

- [ ] Add `claims` array to `VerificationResponse` schema
- [ ] Add `url` field to `Article` model and `ArticleResultSchema`
- [ ] Implement full verification logic (verdict, confidence, reasoning)
- [ ] Add per-criterion scoring (content similarity, support ratio, etc.)
- [ ] Implement contextual judgment for out-of-context detection
- [ ] Add normalized `similarity_score` (0-1) per article

## Technical Details

### Content Extraction

- **Posts**: Extracts text from main post content area
- **Comments**: Handles nested comment threads
- **Reels/Photos**: Extracts captions and descriptions
- **Vietnamese Support**: Handles special characters and Unicode properly

### Facebook Compatibility

- Uses `MutationObserver` to detect dynamically loaded content
- Handles Facebook's complex DOM structure with multiple fallback strategies
- Marks processed elements to avoid duplicate processing

### Performance

- **Caching**: Backend uses Redis with SHA256 hashing for duplicate posts
- **Lazy Loading**: Only processes visible posts
- **Efficient Search**: Hybrid retrieval with pgvector + BM25 full-text search

## Development

### Testing Extension Changes

1. Make code changes in `extension/src/`
2. Go to `chrome://extensions/`
3. Click "Reload" button under VeriNews extension
4. Refresh Facebook page to test

### Debugging

**Console Logs**:
- Right-click on Facebook page → "Inspect" → "Console" tab
- Filter by "VeriNews" or check for errors

**Background Worker**:
- Go to `chrome://extensions/`
- Click "Inspect views: service worker" under VeriNews
- View background script logs and errors

**Network Requests**:
- Inspect page → "Network" tab
- Filter by "verify" to see API calls
- Check request/response payloads

## Troubleshooting

### Extension Not Appearing

- Ensure manifest.json is valid (check for syntax errors)
- Verify all file paths in manifest match actual structure
- Check Chrome Extensions page for error messages

### "Disconnected" Status

- Ensure backend is running: `curl http://localhost:8000/api/v1/health`
- Check `config.js` backend URL matches your setup
- Look for CORS errors in browser console

### Verify Button Not Showing

- Check if extension is enabled (icon should be colored, not gray)
- Ensure you're on `facebook.com` domain
- Refresh page after enabling extension
- Check console for JavaScript errors

### API Errors

- **401/403**: Backend authentication issue (VeriNews doesn't require auth)
- **422**: Invalid request format (check request body in Network tab)
- **500**: Backend error (check backend logs)
- **Network Error**: Backend not reachable (check URL and firewall)

## Browser Compatibility

- ✅ Chrome/Chromium 88+
- ✅ Edge 88+
- ⚠️ Firefox: Requires manifest conversion (not tested)
- ❌ Safari: Not supported (MV3 differences)

## Security Notes

- Extension requires `host_permissions: ["<all_urls>"]` to inject into Facebook
- No sensitive data is stored (only enable/disable toggle state)
- All API communication over HTTP/HTTPS (configure in `config.js`)
- Content script isolated from page JavaScript context

## License

Part of the VeriNews project. See main project README for license information.

## Contributing

When making changes to the extension:

1. Test thoroughly on various Facebook content types
2. Check for console errors and warnings
3. Verify backward compatibility with current API
4. Update README if adding new features or changing configuration
5. Follow existing code style and structure

## Support

For issues and questions:
- Check backend logs: `./scripts/verinews logs api`
- Review browser console for client-side errors
- Ensure backend has data: Check crawler status with `./scripts/verinews crawler status`
