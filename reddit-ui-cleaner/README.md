# Reddit UI Cleaner

Hide Reddit's persistent account-ban notice and **Games on Reddit** sidebar section.


**Supported hosts:** `www.reddit.com`, `sh.reddit.com`, `new.reddit.com`

## Behavior

- Detects the English text `this account has been permanently banned` and hides its nearest small banner container.
- Looks for a leaf node with the heading `Games on Reddit` and hides a recognized, reasonably sized sidebar section wrapper.
- Observes dynamically added content and newly encountered open Shadow DOM roots.
- Scans changed nodes rather than rescanning the entire page on every mutation.

## Installation

Install [Violentmonkey](https://violentmonkey.github.io/), install the raw `.user.js` file, and reload Reddit.

## Important

This is **cosmetic only**. It does not remove an account ban, restore posting privileges, change moderation decisions, or interact with Reddit's servers.

## Limitations

Rules depend on English text and recognizable section markup. Games may remain visible if Reddit no longer uses a safe wrapper, since the script deliberately avoids hiding arbitrary ancestors. Closed Shadow DOM roots cannot be inspected. Ban text rendered in multiple nested elements may also evade text matching.
