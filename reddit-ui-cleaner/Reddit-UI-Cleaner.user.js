// ==UserScript==
// @name         Reddit UI Cleaner
// @namespace    https://github.com/browser-tweaks
// @version      1.2.0
// @description  Hide the permanent-ban notice and the Games on Reddit sidebar section (cosmetic only).
// @match        https://www.reddit.com/*
// @match        https://sh.reddit.com/*
// @match        https://new.reddit.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(() => {
  'use strict';
  const BAN_TEXT = 'this account has been permanently banned';
  const GAMES_TEXT = 'games on reddit';
  const observed = new WeakSet();
  const pending = new Set();
  let timer = null;

  function hideForLeaf(el) {
    if (!(el instanceof Element) || el.children.length) return;
    const text = (el.textContent || '').trim().toLowerCase();
    if (text.includes(BAN_TEXT)) {
      let target = el;
      while (target.parentElement) {
        const parentText = (target.parentElement.textContent || '').trim().toLowerCase();
        if (parentText.includes(BAN_TEXT) && parentText.length < 250) target = target.parentElement;
        else break;
      }
      target.style.setProperty('display', 'none', 'important');
    }
    if (text === GAMES_TEXT) {
      // Intentionally avoid hiding an unknown ancestor if Reddit changes structure.
      const section = el.closest('faceplate-expandable-section-helper, details, section');
      if (section && section.textContent.length < 1800) section.style.setProperty('display', 'none', 'important');
    }
  }
  function scan(root) {
    if (!root) return;
    if (root instanceof Element) hideForLeaf(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
    let el;
    while ((el = walker.nextNode())) {
      hideForLeaf(el);
      if (el.shadowRoot) { watch(el.shadowRoot); scan(el.shadowRoot); }
    }
  }
  function flush() {
    timer = null;
    for (const root of pending) scan(root);
    pending.clear();
  }
  function queue(root) {
    if (!root) return;
    pending.add(root);
    if (timer === null) timer = setTimeout(flush, 250);
  }
  function watch(root) {
    if (observed.has(root)) return;
    observed.add(root);
    new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'characterData') queue(record.target.parentElement);
        for (const node of record.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) queue(node);
        }
      }
    }).observe(root, { childList:true, characterData:true, subtree:true });
  }
  function start() { if (!document.body) return; watch(document.body); scan(document.body); }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded',start,{once:true});
})();
