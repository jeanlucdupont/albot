// ==UserScript==
// @name         LLM Color Identity
// @namespace    https://github.com/browser-tweaks
// @version      1.0.0
// @description  Visually distinguish AI chat providers using configurable accent colors.
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @match        https://claude.ai/*
// @match        https://gemini.google.com/*
// @match        https://copilot.microsoft.com/*
// @match        https://chat.deepseek.com/*
// @match        https://www.perplexity.ai/*
// @grant        GM_addStyle
// @run-at       document-start
// ==/UserScript==

(() => {
  'use strict';
  // Change these colors to suit your preferences. Colors are not official branding.
  const CONFIG = {
    'chatgpt.com':         { name: 'ChatGPT',    light: '#fbe4e4', dark: '#673333', accent: '#ae4444' },
    'chat.openai.com':     { name: 'ChatGPT',    light: '#fbe4e4', dark: '#673333', accent: '#ae4444' },
    'claude.ai':           { name: 'Claude',     light: '#fff0dc', dark: '#654627', accent: '#ad762f' },
    'gemini.google.com':   { name: 'Gemini',     light: '#e5edff', dark: '#283d66', accent: '#4778c6' },
    'copilot.microsoft.com': { name: 'Copilot', light: '#e8e5ff', dark: '#423262', accent: '#7964bb' },
    'chat.deepseek.com':   { name: 'DeepSeek',   light: '#e2f3ff', dark: '#254b65', accent: '#3484b9' },
    'www.perplexity.ai':   { name: 'Perplexity', light: '#ddf5f1', dark: '#24564e', accent: '#288f85' },
  };
  const settings = CONFIG[location.hostname];
  if (!settings) return;
  const SHOW_LABEL = true;
  const EDGE_WIDTH_PX = 7;
  // ChatGPT retains the original colored margins; other providers get narrow,
  // fixed, pointer-transparent edge strips to avoid depending on their DOM layouts.
  const isChatGPT = settings.name === 'ChatGPT';
  GM_addStyle(`
    :root { --llm-identity-color:${settings.light}; --llm-identity-accent:${settings.accent}; }
    @media(prefers-color-scheme:dark) { :root { --llm-identity-color:${settings.dark}; } }
    ${isChatGPT ? `
      [data-app-action-timeline-scroll] { background: var(--llm-identity-color) !important; }
      [data-thread-user-message-navigation-content="true"],
      [data-thread-scroll-footer="true"] [data-pip-obstacle="thread-footer"] {
        background: var(--app-color-background-surface, var(--main-surface-primary, #fff)) !important;
      }
      [data-app-action-timeline-scroll] div[aria-hidden="true"],
      [data-app-action-timeline-scroll] div[aria-hidden="true"] > div,
      [data-thread-scroll-footer="true"] > div[aria-hidden="true"] { background: none !important; }
    ` : ''}
    #llm-identity-left,#llm-identity-right { position:fixed; top:0; bottom:0; width:${EDGE_WIDTH_PX}px;
      background:var(--llm-identity-accent); z-index:2147483000; pointer-events:none; }
    #llm-identity-left { left:0; } #llm-identity-right { right:0; }
    #llm-identity-label { position:fixed; bottom:12px; right:12px; padding:4px 8px;
      color:white; background:var(--llm-identity-accent); border-radius:5px;
      font:600 11px/1.5 system-ui,sans-serif; z-index:2147483001; pointer-events:none;
      opacity:.87; box-shadow:0 1px 4px #0003; }
  `);
  function mount() {
    if (!document.body || document.getElementById('llm-identity-left')) return;
    for (const side of ['left','right']) {
      const strip = document.createElement('div'); strip.id = `llm-identity-${side}`;
      strip.setAttribute('aria-hidden','true'); document.body.appendChild(strip);
    }
    if (SHOW_LABEL) {
      const label = document.createElement('div'); label.id = 'llm-identity-label';
      label.textContent = settings.name; label.setAttribute('aria-hidden','true'); document.body.appendChild(label);
    }
  }
  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount, { once:true });
})();
