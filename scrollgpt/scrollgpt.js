// ==UserScript==
// @name         ScrollGPT
// @namespace    http://tampermonkey.net
// @version      1.0
// @description  Navigate ChatGPT messages sequentially using Up and Down arrow keys.
// @author       AI Collaborator
// @match        https://chatgpt.com*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    let currentIndex = -1;

    window.addEventListener('keydown', function(e) {
        // Ignore arrow keys if the user is actively typing in a text field or textarea
        if (document.activeElement.tagName === 'TEXTAREA' || document.activeElement.tagName === 'INPUT') {
            return;
        }

        // ChatGPT message containers (handles both user prompts and AI responses)
        const messages = document.querySelectorAll('article, [data-testid^="conversation-turn-"]');
        if (messages.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (currentIndex < messages.length - 1) {
                currentIndex++;
                scrollToMessage(messages[currentIndex]);
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (currentIndex > 0) {
                currentIndex--;
                scrollToMessage(messages[currentIndex]);
            }
        }
    });

    function scrollToMessage(element) {
        // Clear any previous visual highlights
        document.querySelectorAll('.js-nav-highlight').forEach(el => {
            el.style.borderLeft = 'none';
            el.style.paddingLeft = '0px';
        });

        // Add a subtle visual anchor to show which message is active
        element.style.borderLeft = '4px solid #10a37f';
        element.style.paddingLeft = '8px';
        element.classList.add('js-nav-highlight');

        // Smoothly scroll the message into the center of the viewport
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
})();
// ==UserScript==
// @name        New script google.com
// @namespace   Violentmonkey Scripts
// @icon        https://www.gstatic.com/images/branding/searchlogo/ico/favicon.ico
// @version     1.0.0
//
// @match       https://www.google.com/search*
// @grant       none
//
// @author      -
// @description
// ==/UserScript==
