# LLM Color Identity

Identify the current AI chat website at a glance using a distinctive accent color.

**File:** [`LLM-Color-Identity.user.js`](LLM-Color-Identity.user.js)  
**Version:** 1.0.0

## Supported sites and default colors

| Provider | Host | Light background | Edge accent |
| --- | --- | --- | --- |
| ChatGPT | `chatgpt.com` / `chat.openai.com` | `#fbe4e4` | `#ae4444` |
| Claude | `claude.ai` | `#fff0dc` | `#ad762f` |
| Gemini | `gemini.google.com` | `#e5edff` | `#4778c6` |
| Microsoft Copilot | `copilot.microsoft.com` | `#e8e5ff` | `#7964bb` |
| DeepSeek | `chat.deepseek.com` | `#e2f3ff` | `#3484b9` |
| Perplexity | `www.perplexity.ai` | `#ddf5f1` | `#288f85` |

The script displays narrow, non-interactive color strips at the screen edges plus a small provider name in the lower-right corner. For ChatGPT, it also applies the original wider light-red conversation margins via ChatGPT-specific CSS. **Other sites currently use edge strips, not full-width conversation margins.**

## Customize

Edit the `CONFIG` object in the script. The properties `light`, `dark`, and `accent` hold colors for each hostname. `SHOW_LABEL` toggles the provider label; `EDGE_WIDTH_PX` changes strip thickness.

Dark colors follow the OS/browser `prefers-color-scheme` preference. If an AI service has an independent theme setting, the accent may not track it.

## Installation

Install [Violentmonkey](https://violentmonkey.github.io/), install the raw `.user.js` file, and reload a supported site.

## Limitations

Color choices are unofficial. ChatGPT's wide-margin selectors depend on its current interface markup. AI service layout or domain changes may break a specific site's appearance. Very narrow strips can overlay content along the absolute viewport edge, but do not intercept clicks.
