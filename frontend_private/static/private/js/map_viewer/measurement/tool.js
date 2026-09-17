import { DEFAULTS } from '../config.js';
import { isMapDialogOpen, isVisibleMapElement } from '../components/overlay_host.js';
import { coordinateFromPoint, createMeasurement, formatDistance } from './geometry.js';
import { MeasurementRenderer } from './renderer.js';

function viewportBounds() {
    const left = window.visualViewport?.offsetLeft || 0;
    const top = window.visualViewport?.offsetTop || 0;
    return {
        left, top,
        right: left + (window.visualViewport?.width || window.innerWidth),
        bottom: top + (window.visualViewport?.height || window.innerHeight),
    };
}

/** A temporary private-map tool. Map interactions are routed by Interactions. */
export class MeasurementTool {
    constructor({ canActivate = () => true, onActivate = () => {} } = {}) {
        this.canActivate = canActivate;
        this.onActivate = onActivate;
        this.active = false;
        this.available = true;
        this.measurements = [];
        this.start = null;
        this.nextId = 0;
        this.listeners = [];
        this.layoutFrame = null;
    }

    onAdd(map) {
        this.map = map;
        this.canvas = map.getCanvas();
        this.host = map.getContainer();
        this.renderer = new MeasurementRenderer(map);
        this.control = document.createElement('div');
        this.control.className = 'mapboxgl-ctrl mapboxgl-ctrl-group measurement-control';
        this.button = document.createElement('button');
        this.button.type = 'button';
        this.button.className = 'mapboxgl-ctrl-icon measurement-button';
        this.button.setAttribute('aria-label', 'Measure distance');
        this.button.setAttribute('aria-pressed', 'false');
        // Trusted static icon, with no user/API interpolation.
        this.button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3 16 13-13 5 5L8 21zM7 12l2 2m2-6 2 2m2-6 2 2"/></svg>';
        this.control.append(this.button);
        this.instructions = document.createElement('section');
        this.instructions.className = 'measurement-instructions';
        this.instructions.setAttribute('aria-label', 'Distance measurement instructions');
        this.instructions.hidden = true;
        const heading = document.createElement('strong');
        heading.textContent = 'Measure distance';
        this.prompt = document.createElement('p');
        this.prompt.className = 'measurement-prompt';
        this.hint = document.createElement('p');
        this.hint.className = 'measurement-hint';
        this.cancelHint = document.createElement('p');
        this.cancelHint.className = 'measurement-hint';
        this.clearHint = document.createElement('p');
        this.clearHint.className = 'measurement-clear-hint';
        this.instructions.append(heading, this.prompt, this.hint, this.cancelHint, this.clearHint);
        this.crosshair = document.createElement('div');
        this.crosshair.className = 'measurement-crosshair';
        this.crosshair.setAttribute('aria-hidden', 'true');
        this.crosshair.hidden = true;
        this.announcement = document.createElement('div');
        this.announcement.className = 'measurement-sr-only';
        this.announcement.setAttribute('role', 'status');
        this.announcement.setAttribute('aria-live', 'polite');
        this.announcement.setAttribute('aria-atomic', 'true');
        this.results = document.createElement('ol');
        this.results.className = 'measurement-sr-only';
        this.results.setAttribute('aria-label', 'Completed distances');
        this.host.append(this.instructions, this.crosshair, this.announcement, this.results);
        this.listen(this.button, 'click', event => {
            event.stopPropagation();
            if (this.active) this.deactivate();
            else this.activate({ keyboard: event.detail === 0 });
        });
        this.listen(this.canvas, 'keydown', event => this.handleKeyDown(event));
        this.listen(this.canvas, 'mouseleave', () => this.hidePreview());
        this.listen(this.canvas, 'touchcancel', () => this.handleCancel());
        this.listen(window, 'blur', () => { this.handleCancel(); this.hidePreview(); });
        this.listen(document, 'focusin', () => this.checkDialog());
        this.listen(window, 'resize', () => this.queueLayout());
        this.listen(window, 'scroll', () => this.queueLayout());
        if (window.visualViewport) {
            this.listen(window.visualViewport, 'resize', () => this.queueLayout());
            this.listen(window.visualViewport, 'scroll', () => this.queueLayout());
        }
        this.onMapMove = () => {
            if (this.active && this.keyboard && !isMapDialogOpen()) this.preview(this.centerPoint());
        };
        map.on('move', this.onMapMove);
        this.onMapRemove = () => this.destroy();
        map.on('remove', this.onMapRemove);
        if (typeof ResizeObserver !== 'undefined') {
            this.resizeObserver = new ResizeObserver(() => this.layout());
            this.resizeObserver.observe(this.host);
        }
        // Legacy managers include dynamically mounted dialogs. Observe visibility,
        // not high-frequency map transforms or source data.
        this.observer = new MutationObserver(records => {
            if (!this.active || !records.some(record => {
                const target = record.target;
                if (!(target instanceof Element) || target.closest('.measurement-instructions, .measurement-control, .measurement-crosshair, .measurement-sr-only, .measurement-live-label')) return false;
                // Inline panel visibility is relevant; canvas/control transforms
                // and other map styles are deliberately ignored.
                return record.attributeName !== 'style' || /panel|modal|dialog/.test(target.id);
            })) return;
            this.queueLayout();
        });
        this.setAvailable(this.available);
        this.layout();
        return this.control;
    }

    listen(target, name, listener) {
        target.addEventListener(name, listener);
        this.listeners.push(() => target.removeEventListener(name, listener));
    }

    isActive() { return this.active; }

    activate({ keyboard = false } = {}) {
        if (this.active || !this.map || !this.available || !this.canActivate() || isMapDialogOpen()) return false;
        this.onActivate();
        this.active = true;
        this.keyboard = keyboard;
        this.touch = !keyboard && Boolean(window.matchMedia?.('(pointer: coarse)').matches);
        this.suspended = false;
        this.savedCursor = this.canvas.style.cursor;
        this.savedDoubleClickZoom = this.map.doubleClickZoom?.isEnabled?.() ?? false;
        this.map.doubleClickZoom?.disable();
        this.canvas.style.cursor = 'crosshair';
        this.button.setAttribute('aria-pressed', 'true');
        this.button.title = 'Turn off measurement and clear all';
        this.instructions.hidden = false;
        this.crosshair.hidden = !keyboard;
        if (keyboard) this.canvas.focus({ preventScroll: true });
        this.updateInstructions();
        this.announce(keyboard ? 'Measurement on. Arrow keys to pan, plus or minus to zoom, and Enter to set the first point.' : 'Measurement on. Set the first point.');
        this.observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'hidden', 'open', 'style'] });
        return true;
    }

    deactivate() {
        if (!this.active) return;
        this.active = false;
        this.observer.disconnect();
        if (this.layoutFrame !== null) cancelAnimationFrame(this.layoutFrame);
        this.layoutFrame = null;
        this.start = null;
        this.gesture = null;
        this.suppressClick = false;
        this.measurements = [];
        this.renderer.clear();
        this.results.replaceChildren();
        this.canvas.style.cursor = this.savedCursor;
        if (this.savedDoubleClickZoom) this.map.doubleClickZoom?.enable();
        this.button.setAttribute('aria-pressed', 'false');
        this.button.title = 'Measure distance';
        this.instructions.hidden = true;
        this.crosshair.hidden = true;
        this.announce('Measurement off. All distances cleared.');
    }

    setAvailable(available) {
        this.available = available;
        if (!available) this.deactivate();
        if (!this.button) return;
        this.button.disabled = !available;
        this.button.title = available ? (this.active ? 'Turn off measurement and clear all' : 'Measure distance') : 'Finish geometry editing to measure';
        this.button.setAttribute('aria-label', available ? 'Measure distance' : 'Finish geometry editing to measure');
    }

    cancelDraft() {
        if (!this.active || !this.start) return false;
        this.start = null;
        this.renderer.setDraft(null);
        this.updateInstructions();
        this.announce('Unfinished measurement cancelled. Set the first point.');
        return true;
    }

    handleClick(event) {
        if (!this.active) return false;
        if (isMapDialogOpen()) return true;
        if (this.suppressClick) { this.suppressClick = false; return true; }
        if (event.originalEvent?.button > 0 || event.originalEvent?.detail > 1) return true;
        this.setInputMode(false, Boolean(event.originalEvent?.sourceCapabilities?.firesTouchEvents) || this.touch);
        this.commit(event.point);
        return true;
    }

    handleMouseDown(event) {
        if (!this.active) return false;
        if (isMapDialogOpen()) return true;
        if (event.originalEvent?.button > 0) return true;
        const touch = Boolean(event.points || event.originalEvent?.touches);
        this.setInputMode(false, touch);
        if (event.points?.length > 1 || event.originalEvent?.touches?.length > 1) {
            this.suppressClick = true;
            this.gesture = { invalid: true };
        } else {
            this.suppressClick = false;
            this.gesture = { point: event.point || event.points?.[0], invalid: false };
        }
        return true;
    }

    handleMouseMove(event) {
        if (!this.active) return false;
        if (isMapDialogOpen()) { this.hidePreview(); return true; }
        const point = event.point || event.points?.[0];
        if (event.points?.length > 1 || event.originalEvent?.touches?.length > 1) {
            this.suppressClick = true;
            if (this.gesture) this.gesture.invalid = true;
            this.hidePreview();
            return true;
        }
        if (this.gesture?.point && point && Math.hypot(point.x - this.gesture.point.x, point.y - this.gesture.point.y) >= DEFAULTS.DRAG.THRESHOLD_PX) {
            this.gesture.invalid = true;
            this.suppressClick = true;
        }
        if (this.gesture?.invalid) return true;
        if (!this.touch) this.setInputMode(false, false);
        this.preview(point);
        return true;
    }

    handleMouseUp() {
        if (!this.active) return false;
        if (this.gesture?.invalid) this.suppressClick = true;
        this.gesture = null;
        return true;
    }

    handleContextMenu(event) {
        if (!this.active) return false;
        event.preventDefault?.();
        event.originalEvent?.preventDefault?.();
        if (!isMapDialogOpen()) this.cancelDraft();
        return true;
    }

    // Gesture cancellation preserves the first endpoint; explicit Cancel/Esc
    // removes it. A browser touchcancel must never complete a measurement.
    handleCancel() {
        if (!this.active) return false;
        this.gesture = null;
        this.suppressClick = true;
        this.hidePreview();
        return true;
    }

    handleKeyDown(event) {
        if (!this.active || document.activeElement !== this.canvas || isMapDialogOpen() || event.repeat) return;
        if (event.key === 'Escape') {
            event.preventDefault();
            this.cancelDraft();
        } else if (event.key === 'Enter') {
            event.preventDefault();
            this.setInputMode(true, false);
            this.commit(this.centerPoint());
        } else if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', '+', '-', '='].includes(event.key)) {
            this.setInputMode(true, false);
        }
    }

    setInputMode(keyboard, touch) {
        if (this.keyboard === keyboard && this.touch === touch) return;
        this.keyboard = keyboard;
        this.touch = touch;
        this.crosshair.hidden = !keyboard;
        this.updateInstructions();
    }

    centerPoint() {
        const rect = this.canvas.getBoundingClientRect();
        const viewport = viewportBounds();
        const left = Math.max(rect.left, viewport.left);
        const right = Math.min(rect.right, viewport.right);
        const top = Math.max(rect.top, viewport.top);
        const bottom = Math.min(rect.bottom, viewport.bottom);
        if (left >= right || top >= bottom) return null;
        // The canvas can retain its minimum height below the visible viewport.
        // Keyboard placement and the reticle must share a target the user sees.
        const x = (left + right) / 2;
        let y = (top + bottom) / 2;
        const instructions = this.instructions.getBoundingClientRect();
        const gap = DEFAULTS.MEASUREMENT.PANEL_GAP_PX;
        if (x >= instructions.left - gap && x <= instructions.right + gap
            && y >= instructions.top - gap && y <= instructions.bottom + gap) {
            // Short landscapes leave the center behind our own instructions.
            // Keep its horizontal position, clear of the left project panels.
            if (instructions.bottom + gap < bottom - gap) y = (instructions.bottom + bottom) / 2;
            else if (instructions.top - gap > top + gap) y = (top + instructions.top) / 2;
            else return null;
        }
        return {
            x: x - rect.left,
            y: y - rect.top,
        };
    }

    commit(point) {
        const coordinate = point && coordinateFromPoint(this.map, point);
        if (!coordinate) {
            this.announce('Choose a visible point on the map, away from the sky or poles.');
            return;
        }
        if (!this.start) {
            this.start = coordinate;
            this.renderer.setDraft({ start: this.start, end: null });
            this.announce('First point set. Set the second point.');
        } else {
            const measurement = createMeasurement(this.start, coordinate, ++this.nextId);
            if (!measurement || measurement.distanceMeters === 0) {
                this.announce('Choose a different point to complete the distance.');
                return;
            }
            this.measurements.push(measurement);
            this.renderer.setMeasurements(this.measurements);
            this.renderer.setDraft(null);
            this.start = null;
            const label = formatDistance(measurement.distanceMeters).label;
            const item = document.createElement('li');
            item.textContent = `Measurement ${this.measurements.length}: ${label}`;
            this.results.append(item);
            this.announce(`Measurement ${this.measurements.length}: ${label}. Set the first point to measure again.`);
        }
        this.updateInstructions();
    }

    preview(point) {
        if (!this.start || !point) return;
        const end = coordinateFromPoint(this.map, point);
        this.renderer.setDraft({ start: this.start, end: end || null });
    }

    hidePreview() {
        if (this.active && this.start) this.renderer.setDraft({ start: this.start, end: null });
    }

    checkDialog() {
        if (!this.active) return;
        const suspended = isMapDialogOpen();
        if (suspended === this.suspended) return;
        this.suspended = suspended;
        this.crosshair.hidden = suspended || !this.keyboard;
        if (suspended) this.hidePreview();
    }

    updateInstructions() {
        if (this.keyboard) {
            this.prompt.textContent = `Press Enter to set point ${this.start ? 'B' : 'A'} at the crosshair.${this.start ? '' : this.measurements.length ? ' Start another measurement.' : ''}`;
            this.hint.textContent = 'Arrow keys move the map. + / − zoom.';
            this.cancelHint.textContent = 'Esc cancels the unfinished line.';
            this.clearHint.textContent = 'Tab to the ruler, then Enter to clear all and exit.';
        } else if (this.touch) {
            this.prompt.textContent = this.start ? 'Tap point B to finish.' : this.measurements.length ? 'Tap point A to measure again.' : 'Tap point A, then tap point B.';
            this.hint.textContent = 'Drag with one finger to move the map. Pinch to zoom.';
            this.clearHint.textContent = 'Tap the ruler again to clear all and exit.';
        } else {
            this.prompt.textContent = this.start ? 'Move the pointer to preview. Left-click point B to finish.' : this.measurements.length ? 'Left-click point A to measure again.' : 'Left-click point A, move the pointer, then left-click point B.';
            this.hint.textContent = 'Hold left button + drag to move the map. Scroll to zoom.';
            this.cancelHint.textContent = 'Right-click or Esc cancels the unfinished line.';
            this.clearHint.textContent = 'Click the ruler again to clear all and exit.';
        }
        this.cancelHint.hidden = this.touch;
        this.layout();
    }

    announce(message) { this.announcement.textContent = message; }

    queueLayout() {
        if (this.layoutFrame !== null || !this.map) return;
        this.layoutFrame = requestAnimationFrame(() => {
            this.layoutFrame = null;
            if (!this.map) return;
            this.checkDialog();
            this.layout();
        });
    }

    layout() {
        if (!this.host) return;
        const rect = this.host.getBoundingClientRect();
        // Desktop layout keeps a minimum map height even on a short screen.
        // Size the control rail for the part the user can actually see.
        const viewport = viewportBounds();
        const visibleHeight = Math.max(0, Math.min(rect.bottom, viewport.bottom) - Math.max(rect.top, viewport.top));
        this.host.classList.toggle('measurement-compact-map', visibleHeight > 0 && visibleHeight < DEFAULTS.MEASUREMENT.COMPACT_HEIGHT_PX);
        if (!this.active) return;
        const gap = DEFAULTS.MEASUREMENT.PANEL_GAP_PX;
        let left = gap;
        let belowPanels = gap;
        for (const panel of this.host.parentElement.querySelectorAll('#project-panel, #project-panel-minimized, #gps-tracks-panel, #gps-tracks-panel-minimized, #gis-layers-panel, #gis-layers-panel-minimized, #gis-geometries-panel, #gis-geometries-panel-minimized')) {
            if (!isVisibleMapElement(panel)) continue;
            const panelRect = panel.getBoundingClientRect();
            if (panelRect.top < rect.top + this.instructions.offsetHeight + gap && panelRect.bottom > rect.top) {
                left = Math.max(left, panelRect.right - rect.left + gap);
                belowPanels = Math.max(belowPanels, panelRect.bottom - rect.top + gap);
            }
        }
        const right = parseFloat(getComputedStyle(this.instructions).right) || gap;
        const maxLeft = Math.max(gap, rect.width - right - DEFAULTS.MEASUREMENT.MIN_INSTRUCTION_WIDTH_PX);
        let top = gap;
        if (left > maxLeft) {
            // A narrow map cannot fit the full left panel and instructions on
            // one row. Prefer the clear area below it, then clamp within the map.
            if (belowPanels + this.instructions.offsetHeight + gap <= rect.height) {
                top = belowPanels;
                left = gap;
            } else left = maxLeft;
        }
        this.instructions.style.left = `${left}px`;
        this.instructions.style.top = `${top}px`;
        const target = this.centerPoint();
        const canvasRect = this.canvas.getBoundingClientRect();
        this.crosshair.hidden = !this.keyboard || !target || isMapDialogOpen();
        if (target) {
            this.crosshair.style.left = `${target.x + canvasRect.left - rect.left}px`;
            this.crosshair.style.top = `${target.y + canvasRect.top - rect.top}px`;
        }
        if (this.keyboard && !this.crosshair.hidden) this.preview(target);
        else if (this.keyboard && !target) this.hidePreview();
    }

    onRemove() { this.destroy(); }

    destroy() {
        if (!this.map) return;
        this.deactivate();
        this.observer?.disconnect();
        this.resizeObserver?.disconnect();
        if (this.layoutFrame !== null) cancelAnimationFrame(this.layoutFrame);
        this.layoutFrame = null;
        this.listeners.splice(0).forEach(remove => remove());
        this.map.off('move', this.onMapMove);
        this.map.off('remove', this.onMapRemove);
        this.renderer.destroy();
        for (const node of [this.control, this.instructions, this.crosshair, this.announcement, this.results]) node.remove();
        this.host.classList.remove('measurement-compact-map');
        this.map = null;
    }
}
