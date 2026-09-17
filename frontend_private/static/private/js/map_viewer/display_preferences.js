import { DEFAULTS } from './config.js';
import { Layers } from './map/layers.js';
import { State, createDefaultDisplayPreferences } from './state.js';

function restorePreferences(stored) {
    if (!stored || Array.isArray(stored) || stored.version !== DEFAULTS.DISPLAY.STORAGE_VERSION) return;
    const preferences = State.displayPreferences;
    if (stored.colorMode === 'project' || stored.colorMode === 'depth') preferences.colorMode = stored.colorMode;
    for (const section of ['categories', 'stationTypes']) {
        if (!stored[section] || typeof stored[section] !== 'object' || Array.isArray(stored[section])) continue;
        for (const id of Object.keys(preferences[section])) {
            if (typeof stored[section][id] === 'boolean') preferences[section][id] = stored[section][id];
        }
    }
}

/** Browser persistence is enabled only by the private viewer's route initializer. */
export const DisplayPreferences = {
    storageAvailable: true,
    _onChange: null,

    init({ persist = false } = {}) {
        this.destroy();
        State.displayPreferences = createDefaultDisplayPreferences();
        this.storageAvailable = true;
        if (persist) {
            let stored;
            try {
                stored = localStorage.getItem(DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES);
            } catch {
                this.storageAvailable = false;
            }
            if (stored) {
                try { restorePreferences(JSON.parse(stored)); } catch { /* Malformed preferences use defaults. */ }
            }
            this._onChange = () => {
                try {
                    localStorage.setItem(DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES, JSON.stringify({
                        version: DEFAULTS.DISPLAY.STORAGE_VERSION,
                        ...State.displayPreferences,
                    }));
                    this.storageAvailable = true;
                } catch {
                    this.storageAvailable = false;
                }
            };
            window.addEventListener('speleo:display-preferences-changed', this._onChange);
        }
        Layers.applyDisplayPreferences();
    },

    reset() {
        State.displayPreferences = createDefaultDisplayPreferences();
        Layers.applyDisplayPreferences();
    },

    destroy() {
        if (this._onChange) window.removeEventListener('speleo:display-preferences-changed', this._onChange);
        this._onChange = null;
    },
};
