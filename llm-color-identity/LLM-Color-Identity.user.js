
// ==UserScript==
// @name         LLM Color Identity
// @namespace    https://github.com/browser-tweaks
// @version      1.3.0
// @description  Identify AI chat providers with a 24px right-side color strip.
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @match        https://claude.ai/*
// @match        https://gemini.google.com/*
// @match        https://copilot.microsoft.com/*
// @match        https://chat.deepseek.com/*
// @match        https://www.perplexity.ai/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(() => {
  'use strict';

  const CONFIG = {
    'chatgpt.com': {
      name: 'ChatGPT', accent: '#0F9E7B'
    },
    'chat.openai.com': {
      name: 'ChatGPT', accent: '#ae4444'
    },
    'claude.ai': {
      name: 'Claude', accent: '#D57755'
    },
    'gemini.google.com': {
      name: 'Gemini', accent: '#F7B80F'
    },
    'copilot.microsoft.com': {
      name: 'Copilot', accent: '#7964bb'
    },
'chat.deepseek.com': {
  name: 'DeepSeek', accent: '#3964FE'
},
    'www.perplexity.ai': {
      name: 'Perplexity', accent: '#288f85'
    }
  };

  const settings = CONFIG[location.hostname];
  if (!settings) return;

  const EDGE_WIDTH_PX = 24;
  const SHOW_LABEL = true;
  const HOST_ID = 'llm-color-identity-overlay';

  let host = null;
  let observingBody = null;

  const observer = new MutationObserver(() => {
    if (!document.body) return;

    if (!host || !host.isConnected ||
        host.parentElement !== document.body) {
      mount();
    }

    watchBody();
  });

  function watchBody() {
    if (!document.body || document.body === observingBody) return;

    observingBody = document.body;
    observer.disconnect();

    observer.observe(document.documentElement, { childList: true });
    observer.observe(observingBody, { childList: true });
  }

  function mount() {
    if (!document.body) return;

    if (host && host.isConnected &&
        host.parentElement === document.body) return;

    if (!host) {
      host = document.createElement('div');
      host.id = HOST_ID;

      const properties = {
        position: 'fixed',
        inset: '0',
        width: '100vw',
        height: '100dvh',
        'pointer-events': 'none',
        'z-index': '2147483647',
        margin: '0',
        padding: '0'
      };

      for (const [name, value] of Object.entries(properties)) {
        host.style.setProperty(name, value, 'important');
      }

      const shadow = host.attachShadow({ mode: 'closed' });
      const style = document.createElement('style');

      style.textContent = `
        :host {
          all: initial;
          pointer-events: none !important;
        }

        .edge {
          position: absolute;
          top: 50px;
          bottom: 0;
          width: ${EDGE_WIDTH_PX}px;
          background: ${settings.accent};
          pointer-events: none;
        }

        .right {
          right: 0;
        }

        .label {
          position: absolute;
          right: 8px;
          top: 60px;
          padding: 4px 8px;
          border-radius: 6px;
          background: ${settings.accent};
          color: white;
          font: 600 11px/1.4 system-ui, sans-serif;
          opacity: 0.9;
          box-shadow: 0 1px 4px rgba(0,0,0,0.2);
          pointer-events: none;
        }

        @media print {
          .edge, .label {
            display: none !important;
          }
        }
      `;

      shadow.append(style);

      const edge = document.createElement('div');
      edge.className = 'edge right';
      edge.setAttribute('aria-hidden', 'true');
      shadow.append(edge);

      if (SHOW_LABEL) {
        const label = document.createElement('div');
        label.className = 'label';
        label.textContent = settings.name;
        label.setAttribute('aria-hidden', 'true');
        shadow.append(label);
      }
    }

    document.body.append(host);
  }

  function initialize() {
    mount();
    watchBody();
  }

  if (document.body) {
    initialize();
  } else {
    document.addEventListener('DOMContentLoaded', initialize, {
      once: true
    });
  }
})();
