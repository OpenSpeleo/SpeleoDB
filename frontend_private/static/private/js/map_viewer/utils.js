"use strict";

export const deepCopy = (obj) => JSON.parse(JSON.stringify(obj));

export function qs(selector, root = document) {
    return root.querySelector(selector);
}

export function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
}

export function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}


