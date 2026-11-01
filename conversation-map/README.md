# ChatGPT Conversation Map

An on-page searchable outline of conversation turns, with quick jumping and user-prompt filtering.

**File:** [`Conversation-Map.user.js`](Conversation-Map.user.js)  
**Version:** 1.0.0  
**Supported hosts:** `chatgpt.com`, `chat.openai.com`

## How to use

1. Install the raw `.user.js` file using Violentmonkey and refresh ChatGPT.
2. Click **Map** in the lower-left corner, or press `Alt+Shift+M`.
3. Search turn content, or uncheck **User prompts only** to include assistant responses.
4. Click a result to scroll to that turn; a green outline marks it.

The list is rebuilt after conversation changes with a small debounce. It resets the search when navigation changes to a different conversation URL. The panel only exists locally in the browser.

## Limitations

**This is not a complete historical index or an export tool.** It can only map messages currently present in the page DOM. ChatGPT may virtualize, lazily load, or remove old turns, so longer conversations might show only part of the history. The extracted summaries are truncated to 240 characters and might include some UI text depending on the current markup. There is no server-side search.

DOM changes may affect author detection, summary extraction, or navigation. Syntax has been checked, but live browser compatibility has not yet been confirmed.
