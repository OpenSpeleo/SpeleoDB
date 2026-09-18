import { DEFAULTS } from '../config.js';
import { DisplayPreferences } from '../display_preferences.js';
import { State } from '../state.js';
import { Layers } from '../map/layers.js';
import { depthFromFeet, depthToFeet, isValidDepthLimit } from '../map/depth.js';
import { containDialogTab } from './dialog_focus.js';
import { MapManagersMenu } from './managers_menu.js';

/** Stable data-category/data-station-type hooks identify the shared preference keys. */
function createSwitch(id, label, preference) {
    const row = document.createElement('label');
    row.className = 'map-settings-switch-row';
    const text = document.createElement('span');
    text.textContent = label;
    const control = document.createElement('span');
    control.className = 'toggle-switch';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.setAttribute('role', 'switch');
    input.dataset[preference] = id;
    const slider = document.createElement('span');
    slider.className = 'toggle-slider';
    slider.setAttribute('aria-hidden', 'true');
    control.append(input, slider);
    row.append(text, control);
    return row;
}

/** Private viewer presentation only; shared map modules own preference effects. */
export const MapSettings = {
    dialog: null,
    trigger: null,
    listeners: [],
    restoreFocus: true,
    depthDraftDirty: false,

    init({ managers = {} } = {}) {
        this.destroy();
        this.dialog = document.getElementById('map-settings-dialog');
        this.trigger = document.getElementById('map-settings-button');
        if (!this.dialog || !this.trigger) return;
        this.renderVisibility();
        this.setError('');
        MapManagersMenu.init({ managers });

        this.listen(this.trigger, 'click', () => this.open());
        this.dialog.querySelectorAll('[data-settings-close]').forEach(button => {
            this.listen(button, 'click', () => this.close());
        });
        this.listen(this.dialog, 'cancel', event => {
            event.preventDefault();
            event.stopPropagation();
            this.close();
        });
        this.listen(this.dialog, 'keydown', event => {
            // Settings form keys must never reach map or geometry shortcuts.
            event.stopPropagation();
            if (event.key === 'Enter' && event.target.id === 'map-settings-depth-value') {
                event.preventDefault();
                this.commitDepthLimit();
            } else if (event.key === 'Escape') {
                event.preventDefault();
                this.close();
            } else if (event.key === 'Tab') {
                containDialogTab(event, this.dialog);
            }
        });
        this.listen(this.dialog, 'click', event => {
            if (event.target !== this.dialog) return;
            const bounds = this.dialog.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right
                || event.clientY < bounds.top || event.clientY > bounds.bottom) {
                this.close();
            }
        });
        this.listen(this.dialog, 'close', () => {
            this.trigger.setAttribute('aria-expanded', 'false');
            if (this.restoreFocus) this.trigger.focus();
        });
        this.listen(this.dialog, 'change', event => this.handleChange(event));
        this.listen(this.dialog.querySelector('#map-settings-depth-value'), 'input', () => {
            this.depthDraftDirty = true;
            this.validateDepthLimit();
        });
        this.listen(this.dialog.querySelector('#map-settings-depth-clear'), 'click', () => {
            this.dialog.querySelector('#map-settings-depth-value').value = '';
            this.depthDraftDirty = true;
            this.commitDepthLimit();
        });
        this.listen(document.getElementById('map-settings-reset'), 'click', () => this.reset());
        this.listen(window, 'speleo:display-preferences-changed', () => this.sync());

        this.sync();
    },

    listen(target, event, handler) {
        if (!target) return;
        target.addEventListener(event, handler);
        this.listeners.push(() => target.removeEventListener(event, handler));
    },

    renderVisibility() {
        const container = this.dialog.querySelector('#map-settings-visibility');
        container.replaceChildren();
        DEFAULTS.DISPLAY.CATEGORIES.forEach(category => {
            container.append(createSwitch(category.id, category.label, 'category'));
            if (category.id !== 'surveyStations') return;
            const details = document.createElement('details');
            details.className = 'map-settings-station-types';
            const summary = document.createElement('summary');
            const label = document.createElement('span');
            label.textContent = 'Station types';
            const count = document.createElement('span');
            count.id = 'map-settings-type-count';
            count.className = 'map-settings-type-count';
            summary.append(label, count);
            const types = document.createElement('fieldset');
            types.className = 'map-settings-types';
            const legend = document.createElement('legend');
            legend.className = 'sr-only';
            legend.textContent = 'Survey station types';
            types.append(legend);
            DEFAULTS.DISPLAY.STATION_TYPES.forEach(type => {
                types.append(createSwitch(type.id, type.label, 'stationType'));
            });
            details.append(summary, types);
            container.append(details);
        });
    },

    handleChange(event) {
        const input = event.target;
        if (input.id === 'map-settings-depth-value') {
            this.commitDepthLimit();
            return;
        } else if (input.name === 'map-settings-depth-unit' && input.checked) {
            const unit = input.value;
            if (this.commitDepthLimit()) {
                Layers.setDepthLimit(State.displayPreferences.depthLimitFeet, unit);
            }
        } else if (input.name === 'map-settings-color-mode' && input.checked) {
            Layers.setColorMode(input.value);
        } else if (input.dataset.category) {
            Layers.setCategoryVisibility(input.dataset.category, input.checked);
        } else if (input.dataset.stationType) {
            Layers.setStationTypeVisibility(input.dataset.stationType, input.checked);
        }
        this.sync();
    },

    validateDepthLimit() {
        const input = this.dialog.querySelector('#map-settings-depth-value');
        const value = input.value.trim() === '' ? null
            : depthToFeet(input.valueAsNumber, State.displayPreferences.depthUnit);
        const valid = !input.validity.badInput && isValidDepthLimit(value);
        const message = valid ? '' : 'Enter a number greater than zero, or leave blank for the full range.';
        input.setCustomValidity(message);
        input.setAttribute('aria-invalid', String(!valid));
        const error = this.dialog.querySelector('#map-settings-depth-error');
        error.textContent = message;
        error.hidden = valid;
        this.dialog.querySelector('#map-settings-depth-clear').hidden = valid && value === null;
        return { valid, value };
    },

    commitDepthLimit() {
        // Unit changes must preserve canonical feet, not reconvert a rounded label.
        if (!this.depthDraftDirty) return true;
        const { valid, value } = this.validateDepthLimit();
        if (!valid) return false;
        this.depthDraftDirty = false;
        Layers.setDepthLimit(value, State.displayPreferences.depthUnit);
        this.syncDepthLimit();
        return true;
    },

    syncDepthLimit() {
        const { colorMode, depthLimitFeet, depthUnit } = State.displayPreferences;
        const details = this.dialog.querySelector('#map-settings-depth-limit');
        details.hidden = colorMode !== 'depth';
        const limited = depthLimitFeet !== null;
        details.classList.toggle('has-limit', limited);
        const value = limited ? String(Number(depthFromFeet(depthLimitFeet, depthUnit)
            .toPrecision(DEFAULTS.DEPTH.INPUT_SIGNIFICANT_DIGITS))) : '';
        this.dialog.querySelector('#map-settings-depth-summary').textContent = limited
            ? `${value} ${depthUnit}` : 'Full range';
        this.dialog.querySelectorAll('[name="map-settings-depth-unit"]').forEach(input => {
            input.checked = input.value === depthUnit;
        });
        if (!this.depthDraftDirty) {
            this.dialog.querySelector('#map-settings-depth-value').value = value;
            this.validateDepthLimit();
        }
    },

    sync() {
        if (!this.dialog || !State.displayPreferences) return;
        const preferences = State.displayPreferences;
        this.syncDepthLimit();
        this.dialog.querySelectorAll('[name="map-settings-color-mode"]').forEach(input => {
            input.checked = input.value === preferences.colorMode;
        });
        this.dialog.querySelectorAll('[data-category]').forEach(input => {
            input.checked = preferences.categories[input.dataset.category];
        });
        this.dialog.querySelectorAll('[data-station-type]').forEach(input => {
            input.checked = preferences.stationTypes[input.dataset.stationType];
        });
        this.dialog.querySelector('.map-settings-types').disabled = !preferences.categories.surveyStations;
        const count = DEFAULTS.DISPLAY.STATION_TYPES.filter(type => preferences.stationTypes[type.id]).length;
        this.dialog.querySelector('#map-settings-type-count').textContent = preferences.categories.surveyStations
            ? `${count} of ${DEFAULTS.DISPLAY.STATION_TYPES.length} selected`
            : 'Survey stations off';
    },

    reset() {
        try {
            this.depthDraftDirty = false;
            this.dialog.querySelector('#map-settings-depth-limit').open = false;
            DisplayPreferences.reset();
            this.setError('');
        } catch {
            this.setError('Unable to reset display settings. Please try again.');
        }
        this.sync();
    },

    setError(message) {
        const error = this.dialog.querySelector('#map-settings-error');
        error.textContent = message;
        error.hidden = !message;
    },

    open() {
        if (!this.dialog || this.dialog.open) return;
        MapManagersMenu.close({ restoreFocus: false });
        this.sync();
        this.restoreFocus = true;
        this.dialog.showModal();
        this.trigger.setAttribute('aria-expanded', 'true');
        this.dialog.querySelector('#map-settings-title').focus({ preventScroll: true });
    },

    close({ restoreFocus = true } = {}) {
        if (!this.dialog?.open) return;
        this.restoreFocus = restoreFocus;
        this.dialog.close();
    },

    destroy() {
        this.close({ restoreFocus: false });
        this.listeners.forEach(remove => remove());
        this.listeners = [];
        if (this.trigger) this.trigger.setAttribute('aria-expanded', 'false');
        this.dialog = null;
        this.trigger = null;
        this.depthDraftDirty = false;
        MapManagersMenu.destroy();
    },
};
