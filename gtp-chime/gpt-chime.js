// ==UserScript==
// @name         GPT Chime
// @namespace    local.chatgpt-tools
// @version      1.3.1
// @description  Plays a chime when ChatGPT's Stop button disappears after generation.
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(() => {
  'use strict';
  if (window.top !== window.self || window.__chatgptChimeV131) return;
  window.__chatgptChimeV131 = true;

  const STORAGE_KEY = 'cgpt-completion-chime-enabled';
  const STOP_SELECTOR = 'button[aria-label="Stop" i], button[aria-label="Stop generating" i], button[data-testid="stop-button" i]';
  const POLL_MS = 150;
  const STOP_GONE_GRACE_MS = 850;

  let enabled = localStorage.getItem(STORAGE_KEY) !== 'false';
  let audioContext;
  let state = 'Idle';
  let lastTrigger = 'none';
  let generationSeen = false;
  let stopGoneSince = null;
  let cancelled = false;
  let lastStopVisible = false;

  function visible(el) {
    return !!(el && el.isConnected && el.getClientRects().length);
  }

  function hasStop() {
    return [...document.querySelectorAll(STOP_SELECTOR)].some(visible);
  }

  function audio() {
    try {
      if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
      if (audioContext.state === 'suspended') void audioContext.resume().catch(() => {});
      return audioContext;
    } catch (error) {
      console.warn('[ChatGPT Chime] Unable to initialize audio:', error);
      return null;
    }
  }

  function chime() {
    const ctx = audio();
    if (!ctx || ctx.state !== 'running') {
      console.warn('[ChatGPT Chime] Audio is not unlocked; click the page or toggle the chime on.');
      return false;
    }
    const t = ctx.currentTime + 0.02;
    for (const [frequency, offset] of [[660, 0], [880, 0.16], [660, 0.32]]) {
      const oscillator = ctx.createOscillator();
      const gain = ctx.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, t + offset);
      gain.gain.exponentialRampToValueAtTime(0.11, t + offset + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + offset + 0.30);
      oscillator.connect(gain);
      gain.connect(ctx.destination);
      oscillator.start(t + offset);
      oscillator.stop(t + offset + 0.31);
    }
    return true;
  }

  // Browser audio playback often requires a user gesture first.
  document.addEventListener('pointerdown', () => { if (enabled) audio(); }, { capture: true, passive: true });
  document.addEventListener('keydown', () => { if (enabled) audio(); }, { capture: true });

  const toggle = document.createElement('button');
  toggle.id = 'cgpt-chime-toggle';
  toggle.type = 'button';
  toggle.setAttribute('aria-label', 'Toggle ChatGPT Chime');
  // Match Prompt Library v1.2.2: 24px circle, left 13px, bottom 117px.
  // Place this button 10px above it: 117 + 24 + 10 = 151px.
  Object.assign(toggle.style, {
    position: 'fixed', bottom: '151px', left: '13px', zIndex: '2147483646',
    width: '24px', height: '24px', borderRadius: '50%', border: '1px solid #7778',
    background: 'var(--main-surface-primary, #222)', color: 'var(--text-primary, #fff)',
    fontSize: '13px', lineHeight: '1', textAlign: 'center', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    opacity: '0.8', padding: '0', boxShadow: '0 2px 8px #0002'
  });

  function updateStatus(newState) {
    if (state === newState) return;
    state = newState;
    render();
    console.debug('[ChatGPT Chime]', state);
  }

  function render() {
    toggle.textContent = enabled ? '♪' : '×';
    toggle.style.opacity = enabled ? '0.8' : '0.4';
    toggle.title = `ChatGPT Chime: ${enabled ? 'ON' : 'OFF'}\nDetector: ${state}\nLast trigger: ${lastTrigger}\nStop button visible: ${lastStopVisible ? 'yes' : 'no'}\nClick to toggle; enabling plays a preview.`;
  }

  function inspect() {
    const stopVisible = hasStop();
    lastStopVisible = stopVisible;
    if (stopVisible) {
      if (!generationSeen) {
        generationSeen = true;
        cancelled = false;
        lastTrigger = 'Stop button appeared';
        updateStatus('Generating · Stop detected');
      }
      stopGoneSince = null;
    } else if (generationSeen) {
      if (cancelled) {
        generationSeen = false;
        stopGoneSince = null;
        updateStatus('Stopped by user · no chime');
      } else {
        if (stopGoneSince === null) stopGoneSince = Date.now();
        updateStatus('Stop disappeared · confirming completion');
        if (Date.now() - stopGoneSince >= STOP_GONE_GRACE_MS) {
          generationSeen = false;
          stopGoneSince = null;
          lastTrigger = 'Stop button disappeared';
          const played = enabled && chime();
          updateStatus(played ? 'Completed · chime played' : enabled ? 'Completed · audio unavailable' : 'Completed · muted');
        }
      }
    }
    render();
  }

  // A user pressing Stop means cancellation, not natural completion.
  document.addEventListener('pointerdown', (event) => {
    if (event.target?.closest?.(STOP_SELECTOR)) cancelled = true;
  }, true);
  document.addEventListener('click', (event) => {
    if (event.target?.closest?.(STOP_SELECTOR)) cancelled = true;
  }, true);

  toggle.addEventListener('click', () => {
    enabled = !enabled;
    localStorage.setItem(STORAGE_KEY, String(enabled));
    if (enabled) chime();
    render();
  });
  (document.body || document.documentElement).appendChild(toggle);

  // Do not play a chime just because the page loads during an existing response.
  // If generation is already in progress, track its natural completion as usual.
  lastStopVisible = hasStop();
  if (lastStopVisible) {
    generationSeen = true;
    lastTrigger = 'Stop button visible on load';
    state = 'Generating · Stop detected';
  }
  render();

  // Polling catches transitions even when React replaces entire controls.
  setInterval(inspect, POLL_MS);
  console.info('[ChatGPT Chime] v1.3.1 ready; completion is detected from the Stop button.');
})();
