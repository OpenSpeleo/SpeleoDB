"use strict";

const store = {
    map: null,
    projectVisibility: new Map(),
};

const events = new Map();

export function setMap(map) {
    store.map = map;
}

export function getMap() {
    return store.map;
}

export function on(event, handler) {
    const set = events.get(event) || new Set();
    set.add(handler);
    events.set(event, set);
}

export function off(event, handler) {
    const set = events.get(event);
    if (!set) return;
    set.delete(handler);
}

export function emit(event, payload) {
    const set = events.get(event);
    if (!set) return;
    set.forEach(fn => {
        try { fn(payload); } catch (err) { console.error(`[state.emit] ${event} handler error`, err); }
    });
}

export const state = { setMap, getMap, on, off, emit, store };


