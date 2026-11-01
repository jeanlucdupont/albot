# ScrollGPT

Keyboard navigation for ChatGPT conversation turns. Avoids replacing normal Up/Down scrolling.


**Version:** 1.1.0  
**Supported hosts:** `chatgpt.com`, `chat.openai.com`

## Controls

| Shortcut | Action |
| --- | --- |
| `Alt+Down` | Next loaded conversation turn |
| `Alt+Up` | Previous loaded conversation turn |
| `Alt+Shift+Down` | Next loaded user turn |
| `Alt+Shift+Up` | Previous loaded user turn |

The first shortcut invocation selects the loaded turn nearest the viewport center; subsequent shortcuts advance from that selection. A green outline marks the selected turn. Keys are ignored while editing an input, textarea, or contenteditable field.

## Installation

Install [Violentmonkey](https://violentmonkey.github.io/), open the raw `.user.js` file, and install; refresh ChatGPT. Alternatively paste the contents into a new script.

## Changes from the original

- Removed unrelated second userscript metadata block.
- Replaced global arrow interception with modifier-key shortcuts.
- Ignored editable fields and added prompt-only navigation.
- Eliminated duplicate turn matching when ChatGPT exposes dedicated turn selectors.
- Uses a CSS class for reversible highlighting instead of modifying padding and borders.
- Resets selection when browser navigation changes conversation URL.

## Limitations

Only currently loaded turns are navigable; virtualized history may be missing. ChatGPT DOM selector changes may require an update. The first jump positions to the nearest turn rather than always jumping to the first message. Browser/OS keyboard shortcuts may conflict.
