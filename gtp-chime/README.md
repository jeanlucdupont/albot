# GPT Chime

**A small notification sound when ChatGPT finishes responding.**

<img width="277" height="171" alt="image" src="https://github.com/user-attachments/assets/49942c2a-97f1-4f9b-9b71-4e64bc283afa" />


When ChatGPT takes a while to generate an answer, switch to another task. GPT Chime plays a short three-note sound when the response completes, so you know when to come back.

GPT Chime is a lightweight [Violentmonkey](https://violentmonkey.github.io/) userscript for ChatGPT. No accounts, API keys, external libraries, or separate audio files are required.

## Features

- **Completion notification:** Plays a short, three-note chime when ChatGPT finishes generating.
- **Cancellation aware:** Does not chime when you click ChatGPT's **Stop** button.
- **One-click mute:** A compact button in the lower-left corner enables or disables the sound.
- **Remembers your choice:** Saves the on/off preference in the browser's local storage for the ChatGPT site.
- **Audio preview:** Attempts to play the chime when you turn it back on.
- **Self-contained:** Uses the browser's Web Audio API; no sound file or external service is needed.

## Installation

1. Install the [Violentmonkey](https://violentmonkey.github.io/) browser extension.
2. Open the [GPT Chime script](https://github.com/jeanlucdupont/albot/blob/main/gtp-chime/gpt-chime.js) and copy its contents.
3. In Violentmonkey, create a **new userscript**, replace the template with the copied code, and save it.
4. Open or refresh [ChatGPT](https://chatgpt.com/).
5. Click somewhere on the ChatGPT page if necessary to allow the browser to initialize audio playback.

The script runs on both `chatgpt.com` and `chat.openai.com`.

## Usage

Look for a small circular control near the **bottom-left** corner of the ChatGPT page:

| Icon | Meaning |
| --- | --- |
| `♪` | Chime enabled (default) |
| `×` | Chime disabled |

Click the control to toggle the sound. When enabled, the script attempts to play a preview. Hover over the control to view the detector state, last trigger, and whether the Stop button is visible.

The button is positioned just above the [Prompt Library](https://github.com/jeanlucdupont/albot/tree/main/prompt-library) userscript's control when both scripts use their intended positions. **Prompt Library is optional**; GPT Chime also works on its own.

## How it works

GPT Chime watches for the **Stop** button that ChatGPT displays while generating a response.

1. A visible Stop button indicates that generation is in progress.
2. When that button disappears, the script waits briefly to confirm the transition.
3. If generation ended normally and notifications are enabled, it plays the chime.
4. If you clicked **Stop**, it treats the response as cancelled and stays silent.

The script checks every **150 ms** and uses an **850 ms** confirmation period after the Stop button disappears. Its three sine-wave notes are generated locally at **660 Hz → 880 Hz → 660 Hz**.

## Troubleshooting

**No sound after installing?** Browser autoplay restrictions may block audio until you interact with the page. Click on ChatGPT, then toggle the chime off and back on. Also check the tab's mute status and your system volume.

**No sound after a completed answer?** Hover over the control to inspect the detector state. GPT Chime relies on ChatGPT's Stop button; changes to ChatGPT's interface may require updating the script's button selectors.

**A delay before the sound?** A short delay is intentional to distinguish a completed response from a temporary interface change. Browser throttling may add more delay in background tabs.

**Want to change the sound or button position?** Edit `gpt-chime.js`. The note frequencies and start offsets are defined in `chime()`, and the button position is configured in the `toggle.style` object.

## Privacy

The userscript operates in your browser. It checks whether ChatGPT's Stop control is visible and stores only the chime's enabled/disabled setting in local storage. It does not read or transmit your conversation content, and the script contains no external network requests.

## Compatibility

- **ChatGPT:** `https://chatgpt.com/*` and `https://chat.openai.com/*`
- **Userscript manager:** Violentmonkey
- **Audio:** Requires browser support for the Web Audio API and permission to play audio

Because completion detection depends on ChatGPT's current page controls, future ChatGPT UI changes could affect the script.

## Source

[`gpt-chime.js`](https://github.com/jeanlucdupont/albot/blob/main/gtp-chime/gpt-chime.js) · Current script version: **1.3.1**
