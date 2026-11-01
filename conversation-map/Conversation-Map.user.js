// ==UserScript==
// @name         ChatGPT Conversation Map
// @namespace    https://github.com/browser-tweaks
// @version      1.1.3
// @description  Searchable, navigable map of currently loaded ChatGPT conversation messages.
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(() => {
  'use strict';
  const ID = 'vm-conversation-map';
  const existing = document.getElementById(ID);
  if (existing) return;

  const host = document.createElement('div');
  host.id = ID;
  // Keep the launcher and panel on the left, above ChatGPT's sidebar.
  host.style.cssText = 'position:fixed!important;inset:0!important;width:100vw!important;height:100dvh!important;z-index:2147483646!important;pointer-events:none!important;margin:0!important;padding:0!important;';
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `
    <style>
      :host { all:initial;position:fixed!important;inset:0!important;width:100vw!important;height:100dvh!important;pointer-events:none!important;z-index:2147483646!important;font:13px/1.4 system-ui,sans-serif; }
      * { box-sizing:border-box; }
      button,input { font:inherit; }
      button { cursor:pointer; }
      #toggle { position:fixed;left:66px;bottom:18px;pointer-events:auto;z-index:2;border:0;border-radius:18px;background:#265c52;color:white;padding:9px 14px;box-shadow:0 3px 12px #0006; }
      #panel { position:fixed;left:66px;bottom:64px;width:min(390px,calc(100vw - 82px));max-height:min(75dvh,750px);background:#fff;color:#222;pointer-events:auto;z-index:3;border:1px solid #bac7c2;border-radius:11px;box-shadow:0 10px 36px #0005;display:none;flex-direction:column;overflow:hidden; }
      #panel.open { display:flex; }
      header { padding:11px 13px;background:#265c52;color:#fff;display:flex;align-items:center;justify-content:space-between; }
      #close { color:#222;background:white;border:0;border-radius:5px;padding:3px 9px; }
      #filters { display:grid;gap:8px;padding:11px;border-bottom:1px solid #ddd; }
      input[type="search"] { padding:8px;border:1px solid #aab;border-radius:5px;width:100%;color:#222;background:#fff; }
      #items { overflow:auto;padding:8px;min-height:56px; }
      .turn { width:100%;text-align:left;border:0;background:#fff;color:#222;padding:9px;border-bottom:1px solid #ddd;border-radius:5px;display:grid;gap:3px; }
      .turn:hover,.turn:focus-visible { background:#e4f3ed; }
      .role { font-weight:700;color:#23695b;font-size:11px; }
      .turn.assistant .role { color:#6c5b88; }
      .snippet { overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden; }
      #status { padding:8px 12px;font-size:11px;color:#5b6266;border-top:1px solid #ddd; }
      label { display:flex;align-items:center;gap:5px; }
      @media print { #toggle,#panel { display:none!important; } }
    </style>
    <button id="toggle" type="button" aria-label="Open Conversation Map" title="Conversation Map (Alt+Shift+M)">Map</button>
    <section id="panel" role="dialog" aria-label="Conversation Map" aria-modal="false">
      <header><strong>Conversation Map</strong><button id="close" type="button" aria-label="Close">✕</button></header>
      <div id="filters"><input id="search" type="search" placeholder="Search loaded messages" aria-label="Search conversation turns"><label><input id="only-user" type="checkbox" checked> User prompts only</label></div>
      <div id="items"></div><div id="status" role="status">Currently loaded turns only</div>
    </section>`;
  const $ = id => root.getElementById(id);
  let isOpen = false, lastPath = location.pathname, selected = null, scheduled = false;

  // Current ChatGPT renders virtualized turns using data-turn-key rather than
  // the older conversation-turn-* test IDs / article elements.
  function getTurns() {
    const wrappers = [...document.querySelectorAll('[data-turn-key]')]
      .filter(el => !el.parentElement?.closest('[data-turn-key]'));
    if (wrappers.length) return wrappers;
    const legacy = [...document.querySelectorAll('[data-testid^="conversation-turn-"]')];
    return legacy.length ? legacy : [...document.querySelectorAll('main article')]
      .filter(el => !el.parentElement?.closest('article'));
  }

  function isUser(el) {
    const unit = el.querySelector('[data-chatgpt-search-unit-key]');
    if (unit) {
      const key = unit.getAttribute('data-chatgpt-search-unit-key') || '';
      if (/:user(?:$|:)/.test(key)) return true;
      if (/:assistant(?:$|:)/.test(key)) return false;
    }
    return el.getAttribute('data-message-author-role') === 'user' ||
      !!el.querySelector('[class*="group/user-message"], [data-message-author-role="user"], [data-testid="user-message"]');
  }

  function getText(el, user) {
    let target;
    if (user) {
      target = el.querySelector('[class*="group/user-message"]') ||
        el.querySelector('[data-message-author-role="user"]') ||
        el.querySelector('[data-testid="user-message"]');
    } else {
      target = el.querySelector('[data-chatgpt-search-unit-key*="assistant"]') ||
        el.querySelector('[data-message-author-role="assistant"]') ||
        el.querySelector('.markdown') ||
        el.querySelector('[data-message-content]');
    }
    target ||= el;
    const clone = target.cloneNode(true);
    clone.querySelectorAll('button,nav,svg,textarea,script,style,input,[aria-hidden="true"],#vm-conversation-map').forEach(n => n.remove());
    return (clone.innerText || clone.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 240);
  }
  function jump(el) {
    if (selected?.isConnected) selected.classList.remove('vm-map-selected');
    selected = el;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // Do not change inline styles permanently.
    el.animate([{ outline: '3px solid #10a37f' }, { outline: '3px solid transparent' }], { duration: 2200 });
  }
  function render() {
    if (!isOpen) return;
    if (location.pathname !== lastPath) {
      lastPath = location.pathname;
      $('search').value = '';
      selected = null;
    }
    const turns = getTurns();
    const filter = $('search').value.trim().toLowerCase();
    const userOnly = $('only-user').checked;
    const entries = turns.map((el, i) => ({ el, i, user: isUser(el), text: getText(el, isUser(el)) }))
      .filter(e => (!userOnly || e.user) && (!filter || e.text.toLowerCase().includes(filter)));
    const fragment = document.createDocumentFragment();
    for (const e of entries) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `turn${e.user ? '' : ' assistant'}`;
      const role = document.createElement('span');
      role.className = 'role';
      role.textContent = `#${e.i + 1} · ${e.user ? 'You' : 'Assistant'}`;
      const snippet = document.createElement('span');
      snippet.className = 'snippet';
      snippet.textContent = e.text || '(no readable text)';
      button.append(role, snippet);
      button.addEventListener('click', () => jump(e.el));
      fragment.append(button);
    }
    $('items').replaceChildren(fragment);
    $('status').textContent = `${entries.length} shown / ${turns.length} loaded turns. Older messages may not be present.`;
  }
  function setOpen(value) {
    isOpen = value;
    $('panel').classList.toggle('open', value);
    $('toggle').setAttribute('aria-expanded', String(value));
    if (value) { render(); $('search').focus(); }
  }
  $('toggle').addEventListener('click', () => setOpen(!isOpen));
  $('close').addEventListener('click', () => setOpen(false));
  $('search').addEventListener('input', render);
  $('only-user').addEventListener('change', render);
  window.addEventListener('keydown', event => {
    if (event.altKey && event.shiftKey && !event.ctrlKey && !event.metaKey && event.code === 'KeyM') {
      event.preventDefault();
      setOpen(!isOpen);
    } else if (event.key === 'Escape' && isOpen) setOpen(false);
  }, true);

  function mount() {
    if (!document.body) return;
    if (host.parentElement !== document.body) document.body.append(host);
  }
  function onMutation(records) {
    if (records.every(record => host === record.target || host.contains(record.target))) return;
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      mount();
      if (isOpen) render();
    });
  }
  function start() {
    mount();
    new MutationObserver(onMutation).observe(document.documentElement, { childList: true, subtree: true });
    console.info('[Conversation Map] v1.1.3 initialized');
  }
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start, { once: true });
})();
