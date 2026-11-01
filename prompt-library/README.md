# Prompt Library for AI Chats

Store reusable prompts locally and insert or copy them when composing messages to AI assistants.

**File:** [`Prompt-Library.user.js`](Prompt-Library.user.js)  
**Version:** 1.0.0  
**Supported sites:** ChatGPT, Claude, Gemini, Microsoft Copilot, DeepSeek, and Perplexity (hosts listed in userscript metadata).

## How to use

1. Install the raw `.user.js` file with Violentmonkey, then reload an AI chat page.
2. Click **Prompts** near the lower-right corner, or press `Alt+Shift+P`.
3. Choose **New prompt**, enter a title and prompt text, then **Save**.
4. Search by title or body; use **Insert**, **Copy**, **Edit**, or **Delete**.

**Insert** attempts to place the prompt in a visible editor. It **does not submit the message**. If the editor is not found, or refuses insertion, the script copies the text to the clipboard and shows a notification. This is a best-effort cross-site feature; editors may change.

## Import / export

**Export JSON** downloads `prompt-library.json` containing an array of `{ "title": "...", "body": "..." }` objects. **Import JSON** validates the file and asks before **replacing the entire library**. Import does not merge. Maximum 250 saved prompts, 100 characters per title, 20,000 per body, and 5 MB per import file.

## Storage and privacy

Prompts use Violentmonkey `GM_getValue` / `GM_setValue` local userscript storage; no external service is contacted by this script. It is **not encrypted**, and exported JSON is plaintext. Avoid storing API keys, passwords, or sensitive business information. Some userscript managers may offer sync or backup behavior under their own settings.

## Limitations

- Composer detection is heuristic and may need maintenance for individual websites.
- On rich editors, insertion uses `document.execCommand('insertText')` for compatibility; this browser API is deprecated. If it fails, the script copies the prompt instead.
- The panel is not a full-screen modal; accessibility and keyboard focus management are intentionally minimal in v1.
- Controls may overlap other page elements on smaller screens.
