// ==UserScript==
// @name         ScrollGPT
// @namespace    https://github.com/browser-tweaks
// @version      1.1.0
// @description  Navigate ChatGPT turns with Alt+Up/Down (Alt+Shift+Up/Down for user prompts).
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(() => {
  'use strict';
  const TURN_SELECTOR = '[data-testid^="conversation-turn-"]';
  const ACTIVE_CLASS = 'scrollgpt-active';
  let active = null;
  let lastConversation = location.pathname;
  const style = document.createElement('style');
  style.textContent = `.${ACTIVE_CLASS}{outline:3px solid #10a37f!important;outline-offset:3px!important;border-radius:6px!important}`;
  document.documentElement.appendChild(style);

  const isTyping = (target) => target instanceof Element && !!target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"]');
  const turns = () => {
    const dedicated = [...document.querySelectorAll(TURN_SELECTOR)];
    if (dedicated.length) return dedicated;
    return [...document.querySelectorAll('main article')].filter(el => !el.parentElement?.closest('article'));
  };
  const isUserTurn = (el) => !!el.querySelector('[data-message-author-role="user"],[data-testid="user-message"],[data-testid="user-message-bubble"]') || el.getAttribute('data-message-author-role') === 'user';
  const visible = el => el.getClientRects().length > 0;
  const clear = () => { active?.classList.remove(ACTIVE_CLASS); active = null; };
  function navigate(direction, userOnly) {
    if (location.pathname !== lastConversation) { clear(); lastConversation = location.pathname; }
    const all = turns().filter(el => visible(el) && (!userOnly || isUserTurn(el)));
    if (!all.length) return;
    let index = active ? all.indexOf(active) : -1;
    // Starting without a selection: find the nearest loaded turn to the viewport center.
    if (index === -1) {
      const middle = window.innerHeight / 2;
      const nearest = all.reduce((best, el, i) => {
        const delta = Math.abs(el.getBoundingClientRect().top - middle);
        return delta < best.delta ? { index: i, delta } : best;
      }, { index: 0, delta: Infinity });
      index = nearest.index;
    } else {
      index = Math.max(0, Math.min(all.length - 1, index + direction));
    }
    clear();
    active = all[index];
    active.classList.add(ACTIVE_CLASS);
    active.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  window.addEventListener('keydown', e => {
    if (e.defaultPrevented || e.repeat || !e.altKey || e.ctrlKey || e.metaKey || isTyping(e.target)) return;
    if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
    e.preventDefault();
    navigate(e.key === 'ArrowDown' ? 1 : -1, e.shiftKey);
  });
  window.addEventListener('popstate', clear);
})();
