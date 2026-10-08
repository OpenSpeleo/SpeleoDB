import type { ColorMode, DisplayCategory, DisplayStationType, StoredDisplayPreferences } from '../../../../../ts-types/domain/map-display.ts';
import { DEFAULTS } from './config.ts';
import { Layers } from './map/layers.ts';
import { Colors } from './map/colors.ts';
import { isValidDepthLimit } from './map/depth.ts';
import { State, createDefaultDisplayPreferences } from './state.ts';
import { flushPreferenceWrites, schedulePreferenceWrite } from './display_preference_storage.ts';

function restorePreferences(value: unknown) {
    // The existing property checks also accept primitive JSON values; this assertion adds no validation.
    const stored = value as StoredDisplayPreferences | null;
    if (!stored || Array.isArray(stored) || stored.version !== DEFAULTS.DISPLAY.STORAGE_VERSION) return;
    const preferences = State.displayPreferences;
    if (Colors.isValidColorMode(stored.colorMode)) preferences.colorMode = stored.colorMode as ColorMode;
    if (isValidDepthLimit(stored.depthLimitFeet)) preferences.depthLimitFeet = stored.depthLimitFeet;
    if (stored.depthUnit === 'ft' || stored.depthUnit === 'm') preferences.depthUnit = stored.depthUnit;
    for (const section of ['categories', 'stationTypes'] as const) {
        if (!stored[section] || typeof stored[section] !== 'object' || Array.isArray(stored[section])) continue;
        for (const id of Object.keys(preferences[section]) as (DisplayCategory | DisplayStationType)[]) {
            if (typeof (stored[section] as Partial<Record<DisplayCategory | DisplayStationType, unknown>>)[id] === 'boolean') (preferences[section] as Partial<Record<DisplayCategory | DisplayStationType, boolean>>)[id] = (stored[section] as Partial<Record<DisplayCategory | DisplayStationType, boolean>>)[id]!;
        }
    }
}

/** Browser persistence is enabled only by the private viewer's route initializer. */
export const DisplayPreferences = {
    storageAvailable: true,
    _onChange: null as (() => void) | null,

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
                schedulePreferenceWrite(DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES,
                    () => ({
                        version: DEFAULTS.DISPLAY.STORAGE_VERSION,
                        ...State.displayPreferences,
                    }),
                    error => { this.storageAvailable = !error; });
            };
            window.addEventListener('speleo:display-preferences-changed', this._onChange);
        }
        void Layers.applyDisplayPreferences();
    },

    reset() {
        State.displayPreferences = createDefaultDisplayPreferences();
        void Layers.applyDisplayPreferences();
    },

    destroy() {
        flushPreferenceWrites(DEFAULTS.STORAGE_KEYS.DISPLAY_PREFERENCES);
        if (this._onChange) window.removeEventListener('speleo:display-preferences-changed', this._onChange);
        this._onChange = null;
    },
};
