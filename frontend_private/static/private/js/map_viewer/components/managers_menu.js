/** Direct manager navigation, separate from display preferences. */
export const MapManagersMenu = {
    trigger: null,
    menu: null,
    listeners: [],

    init({ managers = {} } = {}) {
        this.destroy();
        this.trigger = document.getElementById('map-managers-button');
        this.menu = document.getElementById('map-managers-menu');
        if (!this.trigger || !this.menu) return;
        this.listen(this.trigger, 'click', () => this.menu.hidden ? this.open() : this.close());
        this.listen(this.trigger, 'keydown', event => {
            if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
            event.preventDefault();
            event.stopPropagation();
            this.open({ focusLast: event.key === 'ArrowUp' });
        });
        this.listen(this.menu, 'keydown', event => {
            event.stopPropagation();
            const items = [...this.menu.querySelectorAll('[role="menuitem"]')];
            const index = items.indexOf(document.activeElement);
            if (event.key === 'Escape') {
                event.preventDefault();
                this.close();
            } else if (event.key === 'Tab') {
                event.preventDefault();
                this.close({ restoreFocus: false });
                const target = event.shiftKey ? this.trigger : document.getElementById('map-settings-button');
                (target || this.trigger).focus();
            } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
                event.preventDefault();
                const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1
                    : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
                items[next]?.focus();
            }
        });
        this.listen(document, 'pointerdown', event => {
            if (!this.menu.hidden && !this.menu.contains(event.target) && !this.trigger.contains(event.target)) {
                this.close({ restoreFocus: false });
            }
        });
        const launchers = {
            'station-manager-button': managers.surveyStations,
            'surface-station-manager-button': managers.surfaceStations,
            'landmark-manager-button': managers.landmarks,
        };
        Object.entries(launchers).forEach(([id, launch]) => {
            this.listen(document.getElementById(id), 'click', () => {
                if (!launch) return;
                this.close({ restoreFocus: false });
                launch();
            });
        });
    },

    listen(target, event, handler) {
        if (!target) return;
        target.addEventListener(event, handler);
        this.listeners.push(() => target.removeEventListener(event, handler));
    },

    open({ focusLast = false } = {}) {
        if (!this.menu) return;
        this.menu.hidden = false;
        this.trigger.setAttribute('aria-expanded', 'true');
        const items = this.menu.querySelectorAll('[role="menuitem"]');
        (focusLast ? items[items.length - 1] : items[0])?.focus();
    },

    close({ restoreFocus = true } = {}) {
        if (!this.menu || this.menu.hidden) return;
        this.menu.hidden = true;
        this.trigger.setAttribute('aria-expanded', 'false');
        if (restoreFocus) this.trigger.focus();
    },

    destroy() {
        this.close({ restoreFocus: false });
        this.listeners.forEach(remove => remove());
        this.listeners = [];
        this.trigger = null;
        this.menu = null;
    },
};
