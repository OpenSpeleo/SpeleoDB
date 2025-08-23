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

export function hasProjectWriteAccess(projectId) {
    try {
        const arr = window.projects || [];
        const proj = arr.find(p => p.id === String(projectId));
        if (!proj) return false;
        return proj.permissions === 'READ_AND_WRITE' || proj.permissions === 'ADMIN';
    } catch (_) {
        return false;
    }
}

export function hasProjectAdminAccess(projectId) {
    try {
        const arr = window.projects || [];
        const proj = arr.find(p => p.id === String(projectId));
        if (!proj) return false;
        return proj.permissions === 'ADMIN';
    } catch (_) {
        return false;
    }
}


