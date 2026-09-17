import { API } from '../api.js';
import { Config, DEFAULTS } from '../config.js';
import { Utils } from '../utils.js';
import {
    changeDraft, createGeometryDraft, geometryFromVertices, restoreDraft, validateGeometry,
} from './geometry.js';

const SOURCE = 'gis-geometry-draft-source';
const LAYERS = ['fill', 'line', 'bbox', 'midpoints', 'vertices'].map(role => `gis-geometry-draft-${role}`);

function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function feature(geometry, properties) {
    return { type: 'Feature', properties, geometry };
}

function focusControl(control) {
    if (!control?.isConnected || control === document.body || control === document.documentElement
        || control.matches(':disabled') || control.closest('[hidden], [inert]')) return false;
    control.focus?.({ preventScroll: true });
    return document.activeElement === control;
}

function coordinateFromEvent(event) {
    const location = event.lngLat || event.lngLats?.[0];
    if (!location || !Number.isFinite(location.lng) || !Number.isFinite(location.lat)) return null;
    const limit = DEFAULTS.GIS_GEOMETRY.LONGITUDE_LIMIT;
    const wrap = DEFAULTS.MAP.ANTIMERIDIAN_WRAP_DEGREES;
    return [((location.lng + limit) % wrap + wrap) % wrap - limit, location.lat];
}

function pointFromEvent(event) {
    return event.point || event.points?.[0];
}

function errorText(error) {
    if (error.status === 409) return 'This geometry changed while you were editing. Copy your draft before reloading the saved version.';
    if (error.status === 403 || error.status === 404) return 'You no longer have permission to save this geometry. Your draft has been kept.';
    const fields = error.data?.errors || error.data;
    if (fields && typeof fields === 'object') {
        const message = Object.values(fields).flat().find(value => typeof value === 'string');
        if (message) return message;
    }
    return error.message || 'Unable to save. Your draft has been kept; please try again.';
}

/** One private, transactional editor. The map dispatcher delegates while isActive() is true. */
export const GeometryEditor = {
    init({ map, onSaved = () => {}, onPreview = () => {}, onLoaded = () => {}, palette = [] }) {
        this.destroy();
        this.map = map;
        this.onSaved = onSaved;
        this.onPreview = onPreview;
        this.onLoaded = onLoaded;
        this.palette = palette;
        this.session = null;
        this._opening = false;
        this._keyHandler = event => this.handleKeyDown(event);
        this._leaveHandler = event => {
            if (!this.hasUnsavedChanges()) return;
            event.preventDefault();
            event.returnValue = '';
        };
        this._outsideUp = event => {
            if (!this.session?.drag) return;
            if (!this.map.getContainer().contains(event.target)) this.finishDrag();
        };
        this._cancelDrag = () => this.cancelDrag();
        this._doubleClick = event => {
            if (!this.session || this.session.saving || !this.session.drawing) return;
            event.preventDefault?.();
            if (!this.flushGPS()) return;
            this.session.drawing = false;
            this.session.preview = null;
            this.render();
        };
        document.addEventListener('keydown', this._keyHandler);
        window.addEventListener('beforeunload', this._leaveHandler);
        window.addEventListener('mouseup', this._outsideUp);
        window.addEventListener('touchend', this._outsideUp);
        window.addEventListener('touchcancel', this._cancelDrag);
        window.addEventListener('blur', this._cancelDrag);
        map.on?.('dblclick', this._doubleClick);
        return this;
    },

    isActive() { return Boolean(this.session); },

    hasUnsavedChanges() {
        return Boolean(this.session && (this.session.gpsDirty || this.signature() !== this.session.originalSignature));
    },

    signature() {
        const session = this.session;
        return JSON.stringify([session.name, session.color, session.draft.type, session.draft.vertices]);
    },

    async create() {
        if (this._opening || this.session?.saving) return false;
        if (this.session && this.hasUnsavedChanges()) { this.requestClose(() => this.create()); return false; }
        if (this.session) this.close();
        this.begin(null);
        return true;
    },

    async edit(record) {
        if (this._opening || this.session?.saving) return false;
        if (this.session && this.hasUnsavedChanges()) { this.requestClose(() => this.edit(record)); return false; }
        if (this.session) this.close();
        if (!record?.id || !Config.hasGISGeometryAccess(record.id, 'write')) return false;
        this._opening = true;
        try {
            const fresh = await API.getGISGeometryDetails(record.id);
            Config.upsertGISGeometry(fresh);
            if (!Config.hasGISGeometryAccess(record.id, 'write')) {
                Utils.showNotification('error', 'You no longer have permission to edit this geometry.');
                return false;
            }
            await this.onLoaded(fresh);
            this.begin(fresh);
            return true;
        } catch (error) {
            Utils.showNotification('error', errorText(error));
            return false;
        } finally {
            this._opening = false;
        }
    },

    begin(record) {
        this.session = {
            record: record ? structuredClone(record) : null,
            name: record?.name || '',
            color: Utils.safeCssColor(record?.color || this.palette[Math.floor(Math.random() * this.palette.length)] || DEFAULTS.COLORS.FALLBACK),
            draft: createGeometryDraft(record?.geojson),
            selected: null,
            drawing: !record,
            preview: null,
            drag: null,
            saving: false,
            error: '',
            gpsDirty: false,
            discardRequested: false,
            conflict: false,
            doubleClickEnabled: this.map.doubleClickZoom?.isEnabled?.() ?? false,
        };
        this.session.originalSignature = this.signature();
        this.session.returnFocus = document.activeElement;
        this.map.doubleClickZoom?.disable();
        this.buildUI();
        this.render();
        this.observeViewport();
        this.onPreview(record?.id || null, true);
        const firstControl = record ? this.nodes.root.querySelector('[data-editor-action="close"]')
            : this.nodes.types.querySelector('[aria-pressed="true"]');
        firstControl?.focus({ preventScroll: true });
    },

    observeViewport() {
        this.stopObservingViewport();
        this._queueViewportUpdate = () => {
            if (this._viewportFrame !== null && this._viewportFrame !== undefined) return;
            this._viewportFrame = window.requestAnimationFrame(() => {
                this._viewportFrame = null;
                this.positionWithinViewport();
            });
        };
        window.addEventListener('resize', this._queueViewportUpdate, { passive: true });
        window.addEventListener('scroll', this._queueViewportUpdate, { passive: true, capture: true });
        document.addEventListener('fullscreenchange', this._queueViewportUpdate);
        this._observedVisualViewport = window.visualViewport;
        this._observedVisualViewport?.addEventListener('resize', this._queueViewportUpdate, { passive: true });
        this._observedVisualViewport?.addEventListener('scroll', this._queueViewportUpdate, { passive: true });
        this.nodes.root.addEventListener('focusin', this._queueViewportUpdate);
        this.nodes.root.addEventListener('focusout', this._queueViewportUpdate);
        if (typeof ResizeObserver !== 'undefined') {
            this._viewportObserver = new ResizeObserver(this._queueViewportUpdate);
            this._viewportObserver.observe(this.map.getContainer());
            this._viewportObserver.observe(this.nodes.root);
        }
        this.positionWithinViewport();
    },

    /** Keep the mobile footer inside the visible part of the map, including the on-screen keyboard. */
    positionWithinViewport() {
        if (!this.nodes || !this.session) return;
        const { root } = this.nodes;
        if (window.innerWidth > DEFAULTS.UI.MOBILE_BREAKPOINT) {
            root.style.removeProperty('--geometry-mobile-bottom');
            root.style.removeProperty('--geometry-mobile-max-height');
            return;
        }
        const viewport = window.visualViewport;
        const viewportTop = viewport?.offsetTop || 0;
        const viewportBottom = viewportTop + (viewport?.height || window.innerHeight);
        const edge = DEFAULTS.GIS_GEOMETRY.MOBILE_EDGE_PX;
        const mapContainer = this.map.getContainer();
        let bounds = mapContainer.getBoundingClientRect();
        const focused = root.contains(document.activeElement)
            && document.activeElement.matches('input, textarea');
        if (focused && bounds.top > viewportTop + edge) {
            const requiredHeight = root.querySelector('header').getBoundingClientRect().height
                + root.querySelector('footer').getBoundingClientRect().height
                + document.activeElement.getBoundingClientRect().height + edge * 2;
            const visibleHeight = Math.max(0, Math.min(bounds.bottom, viewportBottom) - Math.max(bounds.top, viewportTop));
            if (visibleHeight < requiredHeight) {
                // Browser keyboard resizing can leave the map below the visible
                // viewport. Scroll only this active editing interaction into view.
                window.scrollBy(0, bounds.top - viewportTop - edge);
                bounds = mapContainer.getBoundingClientRect();
            }
        }
        const visibleHeight = Math.max(0, Math.min(bounds.bottom, viewportBottom) - Math.max(bounds.top, viewportTop));
        const availableHeight = Math.max(0, visibleHeight - edge * 2);
        const heightRatio = focused ? 1 : DEFAULTS.GIS_GEOMETRY.MOBILE_VISIBLE_HEIGHT_RATIO;
        root.style.setProperty('--geometry-mobile-bottom', `${Math.max(0, bounds.bottom - viewportBottom) + edge}px`);
        root.style.setProperty('--geometry-mobile-max-height', `${availableHeight * heightRatio}px`);
    },

    stopObservingViewport() {
        this._viewportObserver?.disconnect();
        this._viewportObserver = null;
        if (this._viewportFrame !== null && this._viewportFrame !== undefined) window.cancelAnimationFrame(this._viewportFrame);
        this._viewportFrame = null;
        if (!this._queueViewportUpdate) return;
        window.removeEventListener('resize', this._queueViewportUpdate);
        window.removeEventListener('scroll', this._queueViewportUpdate, true);
        document.removeEventListener('fullscreenchange', this._queueViewportUpdate);
        this._observedVisualViewport?.removeEventListener('resize', this._queueViewportUpdate);
        this._observedVisualViewport?.removeEventListener('scroll', this._queueViewportUpdate);
        this.nodes?.root.removeEventListener('focusin', this._queueViewportUpdate);
        this.nodes?.root.removeEventListener('focusout', this._queueViewportUpdate);
        this._queueViewportUpdate = null;
    },

    /** data-geometry-editor and data-editor-action are stable runtime/test DOM hooks. */
    buildUI() {
        const root = element('section', 'gis-geometry-editor');
        root.dataset.geometryEditor = '';
        root.setAttribute('aria-labelledby', 'gis-geometry-editor-title');
        const header = element('header', 'gis-geometry-editor__header');
        const heading = element('div');
        heading.append(element('p', 'gis-geometry-editor__eyebrow', 'GIS GEOMETRY'));
        const title = element('h2', '', this.session.record ? 'Edit geometry' : 'New geometry');
        title.id = 'gis-geometry-editor-title';
        heading.append(title);
        const close = this.button('close', 'Close editor', '×');
        close.classList.add('gis-geometry-editor__close');
        header.append(heading, close);
        const body = element('div', 'gis-geometry-editor__body');
        const nameLabel = element('label', 'gis-geometry-editor__field');
        nameLabel.append(element('span', '', 'Name'));
        const name = element('input');
        name.type = 'text';
        name.maxLength = DEFAULTS.GIS_GEOMETRY.NAME_MAX_LENGTH;
        name.value = this.session.name;
        name.placeholder = 'Give this geometry a name';
        name.autocomplete = 'off';
        name.addEventListener('input', () => { this.session.name = name.value; this.refreshUI(); });
        nameLabel.append(name);
        body.append(nameLabel);

        const types = element('div', 'gis-geometry-editor__types');
        types.setAttribute('role', 'group');
        types.setAttribute('aria-label', 'Geometry type');
        for (const [type, label] of [['LineString', 'Line'], ['Polygon', 'Polygon']]) {
            const button = this.button('type', label, label);
            button.dataset.type = type;
            types.append(button);
        }
        body.append(types);
        const colors = element('div', 'gis-geometry-editor__colors');
        colors.setAttribute('role', 'group');
        colors.setAttribute('aria-label', 'Geometry color');
        const palette = [...new Set([...this.palette, this.session.color])].filter(Utils.isValidCssColor);
        for (const color of palette) {
            const button = this.button('color', `Use color ${color}`, '');
            button.dataset.color = color;
            button.style.setProperty('--geometry-swatch', color);
            button.classList.add('gis-geometry-editor__swatch');
            colors.append(button);
        }
        const colorDisclosure = element('details', 'gis-geometry-editor__disclosure');
        const colorSummary = element('summary');
        const currentColor = element('span', 'gis-geometry-editor__current-color');
        colorSummary.append(currentColor, document.createTextNode('Color'));
        colorDisclosure.append(colorSummary, colors);
        body.append(colorDisclosure);

        const hint = element('p', 'gis-geometry-editor__hint');
        const toolbar = element('div', 'gis-geometry-editor__tools');
        toolbar.append(this.button('drawing', 'Finish drawing', 'Finish drawing'), this.button('undo', 'Undo', 'Undo'), this.button('redo', 'Redo', 'Redo'));
        body.append(hint, toolbar);
        const vertices = element('div', 'gis-geometry-editor__vertex-nav');
        vertices.setAttribute('role', 'group');
        vertices.setAttribute('aria-label', 'Select geometry vertex');
        body.append(vertices);
        const gpsDisclosure = element('details', 'gis-geometry-editor__disclosure');
        gpsDisclosure.append(element('summary', '', 'GPS coordinates'));
        const gps = element('form', 'gis-geometry-editor__gps');
        const gpsTitle = element('h3', 'gis-geometry-editor__subheading', 'Add GPS coordinates');
        gps.append(gpsTitle);
        const gpsFields = element('div', 'gis-geometry-editor__gps-fields');
        const latitude = this.coordinateInput('Latitude', `−${DEFAULTS.GIS_GEOMETRY.LATITUDE_LIMIT} to ${DEFAULTS.GIS_GEOMETRY.LATITUDE_LIMIT}`);
        const longitude = this.coordinateInput('Longitude', `−${DEFAULTS.GIS_GEOMETRY.LONGITUDE_LIMIT} to ${DEFAULTS.GIS_GEOMETRY.LONGITUDE_LIMIT}`);
        gpsFields.append(latitude.label, longitude.label);
        gps.append(gpsFields);
        const gpsActions = element('div', 'gis-geometry-editor__tools');
        const apply = this.button('apply-gps', 'Add point', 'Add point');
        apply.type = 'submit';
        gpsActions.append(apply, this.button('deselect', 'Add another point', 'Add another point'), this.button('remove', 'Remove selected point', 'Remove point'));
        gps.append(gpsActions);
        gps.addEventListener('submit', event => { event.preventDefault(); this.applyGPS(); });
        gps.addEventListener('focusout', event => {
            if (this.session?.selected !== null && this.session?.gpsDirty && !gps.contains(event.relatedTarget)) this.applyGPS();
        });
        gpsDisclosure.append(gps);
        body.append(gpsDisclosure);
        const footer = element('footer', 'gis-geometry-editor__footer');
        const area = element('div', 'gis-geometry-editor__area');
        const areaLabel = element('span', '', 'Bounding-box area');
        const areaValue = element('strong');
        area.append(areaLabel, areaValue);
        const progress = element('div', 'gis-geometry-editor__meter');
        const progressFill = element('span');
        progress.append(progressFill);
        const limit = element('p', 'gis-geometry-editor__limit', `The rectangle enclosing all points must stay within ${DEFAULTS.GIS_GEOMETRY.MAX_AREA_M2 / DEFAULTS.GIS_GEOMETRY.SQUARE_METRES_PER_SQUARE_KILOMETRE} km², with at most ${DEFAULTS.GIS_GEOMETRY.MAX_VERTICES} points, to keep the map responsive.`);
        const status = element('p', 'gis-geometry-editor__status');
        status.setAttribute('role', 'status');
        status.setAttribute('aria-live', 'polite');
        const discard = element('div', 'gis-geometry-editor__discard');
        discard.hidden = true;
        discard.append(element('p', '', 'Discard your unsaved changes?'), this.button('keep', 'Keep editing', 'Keep editing'), this.button('discard', 'Discard changes', 'Discard changes'));
        const conflict = element('div', 'gis-geometry-editor__conflict');
        conflict.hidden = true;
        conflict.append(this.button('copy', 'Copy draft GeoJSON', 'Copy draft'), this.button('reload', 'Reload saved geometry', 'Reload saved'));
        const copyFallback = element('textarea', 'gis-geometry-editor__copy-fallback');
        copyFallback.readOnly = true;
        copyFallback.hidden = true;
        copyFallback.setAttribute('aria-label', 'Draft GeoJSON; select and copy to keep your changes');
        conflict.append(copyFallback);
        const actions = element('div', 'gis-geometry-editor__actions');
        const revert = this.button('close', this.session.record ? 'Revert changes' : 'Cancel creation', this.session.record ? 'Revert' : 'Cancel');
        const save = this.button('save', 'Save geometry', 'Save geometry');
        save.classList.add('gis-geometry-editor__save');
        actions.append(revert, save);
        footer.append(area, progress, limit, status, conflict, discard, actions);
        root.append(header, body, footer);
        root.addEventListener('click', event => {
            const action = event.target.closest('[data-editor-action]');
            if (action && action.type !== 'submit') this.performAction(action.dataset.editorAction, action);
        });
        for (const type of ['click', 'mousedown', 'dblclick', 'touchstart', 'contextmenu']) {
            root.addEventListener(type, event => event.stopPropagation());
        }
        root.addEventListener('wheel', event => event.stopPropagation(), { passive: true });
        root.addEventListener('touchmove', event => event.stopPropagation(), { passive: true });
        this.map.getContainer().append(root);
        this.nodes = { root, name, types, colors, currentColor, hint, toolbar, vertices, gps, gpsDisclosure, gpsTitle, latitude: latitude.input, longitude: longitude.input, apply, area, areaValue, progressFill, status, discard, conflict, copyFallback, save };
    },

    button(action, label, text) {
        const button = element('button', action === 'copy' ? 'copy-button' : 'gis-geometry-editor__button', text);
        button.type = 'button';
        button.dataset.editorAction = action;
        button.setAttribute('aria-label', label);
        return button;
    },

    coordinateInput(title, placeholder) {
        const label = element('label', 'gis-geometry-editor__field');
        label.append(element('span', '', title));
        const input = element('input');
        input.type = 'text';
        input.inputMode = 'decimal';
        input.autocomplete = 'off';
        input.placeholder = placeholder;
        input.addEventListener('input', () => { this.session.gpsDirty = true; this.session.error = ''; this.refreshUI(); });
        label.append(input);
        return { label, input };
    },

    performAction(action, button) {
        if (!this.session || this.session.saving) return;
        if (action === 'save') { void this.save(); return; }
        if (action === 'close') { this.requestClose(); return; }
        if (action === 'keep') {
            this.session.discardRequested = false;
            this.session.reloadRequested = false;
            this.session.pendingAction = null;
            this.refreshUI();
            return;
        }
        if (action === 'discard') {
            if (this.session.reloadRequested) void this.reloadSaved();
            else this.close();
            return;
        }
        if (action === 'copy') { void this.copyDraft(); return; }
        if (action === 'reload') {
            this.session.discardRequested = true;
            this.session.reloadRequested = true;
            this.refreshUI();
            this.nodes.discard.querySelector('p').textContent = 'Discard this draft and reload the saved geometry? Copy the draft first to keep it.';
            this.nodes.discard.querySelector('[data-editor-action="discard"]').textContent = 'Discard and reload';
            return;
        }
        // Keyboard commands can arrive before pointer release. Commit the gesture
        // first so undo/remove operate on history rather than a transient snapshot.
        this.finishDrag();
        if (action === 'undo' || action === 'redo') {
            restoreDraft(this.session.draft, action);
            this.select(null);
        } else if (action === 'type' && !this.session.draft.vertices.length && !this.session.record) {
            changeDraft(this.session.draft, [], button.dataset.type);
            this.session.drawing = true;
        } else if (action === 'color') {
            this.session.color = button.dataset.color;
        } else if (action === 'drawing') {
            if (!this.flushGPS()) return;
            this.session.drawing = !this.session.drawing;
            this.session.preview = null;
            this.select(null);
        } else if (action === 'select') {
            if (!this.flushGPS()) return;
            this.session.drawing = false;
            this.select(Number(button.dataset.index));
            this.nodes.gpsDisclosure.open = true;
        } else if (action === 'previous' || action === 'next') {
            if (!this.flushGPS()) return;
            this.session.drawing = false;
            const index = (this.session.selected ?? 0) + (action === 'previous' ? -1 : 1);
            this.select(Math.max(0, Math.min(this.session.draft.vertices.length - 1, index)));
            this.nodes.gpsDisclosure.open = true;
        } else if (action === 'deselect') {
            if (!this.flushGPS()) return;
            this.select(null);
            this.session.drawing = true;
        } else if (action === 'remove' && this.session.selected !== null) {
            const vertices = this.session.draft.vertices.filter((_, index) => index !== this.session.selected);
            changeDraft(this.session.draft, vertices);
            this.select(null);
        }
        this.session.error = '';
        this.render();
    },

    select(index) {
        this.session.selected = index;
        this.session.gpsDirty = false;
        const coordinates = index === null ? null : this.session.draft.vertices[index];
        this.nodes.latitude.value = coordinates ? String(coordinates[1]) : '';
        this.nodes.longitude.value = coordinates ? String(coordinates[0]) : '';
    },

    applyGPS() {
        if (!this.session || this.session.saving) return false;
        const latitudeText = this.nodes.latitude.value.trim();
        const longitudeText = this.nodes.longitude.value.trim();
        const latitude = Number(latitudeText);
        const longitude = Number(longitudeText);
        if (!latitudeText || !longitudeText || !Number.isFinite(latitude) || !Number.isFinite(longitude)
            || Math.abs(latitude) > DEFAULTS.GIS_GEOMETRY.LATITUDE_LIMIT || Math.abs(longitude) > DEFAULTS.GIS_GEOMETRY.LONGITUDE_LIMIT) {
            this.session.error = `Enter a latitude from −${DEFAULTS.GIS_GEOMETRY.LATITUDE_LIMIT} to ${DEFAULTS.GIS_GEOMETRY.LATITUDE_LIMIT} and a longitude from −${DEFAULTS.GIS_GEOMETRY.LONGITUDE_LIMIT} to ${DEFAULTS.GIS_GEOMETRY.LONGITUDE_LIMIT}.`;
            this.refreshUI();
            return false;
        }
        if (this.session.selected !== null) {
            const vertices = this.session.draft.vertices.map(coordinate => [...coordinate]);
            vertices[this.session.selected] = [longitude, latitude];
            changeDraft(this.session.draft, vertices);
        } else if (!this.append([longitude, latitude])) return false;
        this.session.gpsDirty = false;
        this.session.error = '';
        if (this.session.selected === null) { this.nodes.latitude.value = ''; this.nodes.longitude.value = ''; }
        this.render();
        return true;
    },

    flushGPS() { return !this.session.gpsDirty || this.applyGPS(); },

    prospectiveGeometry() {
        const { draft, gpsDirty, selected } = this.session;
        const vertices = draft.vertices.map(coordinate => [...coordinate]);
        if (gpsDirty) {
            const latitude = this.nodes.latitude.value.trim();
            const longitude = this.nodes.longitude.value.trim();
            if (latitude && longitude && Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude))) {
                const position = [Number(longitude), Number(latitude)];
                if (selected === null) vertices.push(position);
                else vertices[selected] = position;
            }
        }
        return geometryFromVertices(draft.type, vertices);
    },

    async copyDraft() {
        if (!this.session || !this.flushGPS()) return false;
        const { session, nodes } = this;
        const text = JSON.stringify(geometryFromVertices(session.draft.type, session.draft.vertices), null, 2);
        try {
            if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
            await navigator.clipboard.writeText(text);
            if (this.session !== session || this.nodes !== nodes) return false;
            nodes.status.textContent = 'Draft GeoJSON copied. Keep it before reloading the saved geometry.';
        } catch {
            if (this.session !== session || this.nodes !== nodes) return false;
            nodes.copyFallback.value = text;
            nodes.copyFallback.hidden = false;
            nodes.copyFallback.focus();
            nodes.copyFallback.select();
            nodes.status.textContent = 'Select and copy the draft below before reloading.';
        }
        return true;
    },

    async reloadSaved() {
        if (!this.session?.record || this.session.saving) return false;
        const session = this.session;
        session.saving = true;
        this.refreshUI();
        try {
            const fresh = await API.getGISGeometryDetails(session.record.id);
            Config.upsertGISGeometry(fresh);
            if (!Config.hasGISGeometryAccess(fresh.id, 'write')) {
                throw Object.assign(new Error('Permission changed'), { status: 403 });
            }
            await this.onLoaded(fresh);
            this.close(true);
            this.begin(fresh);
            return true;
        } catch (error) {
            session.saving = false;
            session.error = `Unable to reload. Your draft has been kept. ${errorText(error)}`;
            this.refreshUI();
            return false;
        }
    },

    append(coordinates, index = null) {
        const { draft } = this.session;
        if (draft.vertices.length >= DEFAULTS.GIS_GEOMETRY.MAX_VERTICES) {
            this.session.error = `A geometry can contain at most ${DEFAULTS.GIS_GEOMETRY.MAX_VERTICES} points.`;
            this.refreshUI();
            return false;
        }
        const vertices = draft.vertices.map(coordinate => [...coordinate]);
        if (index === null && vertices.length && vertices.at(-1)[0] === coordinates[0] && vertices.at(-1)[1] === coordinates[1]) return false;
        vertices.splice(index ?? vertices.length, 0, coordinates);
        changeDraft(draft, vertices);
        return true;
    },

    hit(event) {
        const point = pointFromEvent(event);
        if (!point || !this.map.getLayer(LAYERS.at(-1))) return null;
        const padding = DEFAULTS.GIS_GEOMETRY.HANDLE_QUERY_PADDING;
        const hits = this.map.queryRenderedFeatures([[point.x - padding, point.y - padding], [point.x + padding, point.y + padding]], { layers: LAYERS.slice(-2) });
        return hits.find(item => item.properties.role === 'vertex') || hits[0] || null;
    },

    handleClick(event) {
        if (!this.session) return false;
        if (this.session.saving) return true;
        if (this.session.suppressClick) { this.session.suppressClick = false; return true; }
        if (!this.flushGPS()) return true;
        const hit = this.hit(event);
        if (hit) {
            if (hit.properties.role === 'midpoint' && !this.append(hit.geometry.coordinates, Number(hit.properties.index))) return true;
            this.select(Number(hit.properties.index));
            this.session.drawing = false;
            this.nodes.gpsDisclosure.open = true;
        } else if (this.session.drawing) {
            const coordinates = coordinateFromEvent(event);
            if (coordinates && !this.append(coordinates)) return true;
        } else {
            this.select(null);
        }
        this.session.error = '';
        this.render();
        return true;
    },

    handleMouseDown(event) {
        if (!this.session) return false;
        if (this.session.saving) return true;
        if (event.points?.length > 1) { this.cancelDrag(); return true; }
        if (event.originalEvent?.button !== undefined && event.originalEvent.button !== 0) return true;
        // Mapbox may omit the click after a drag. Suppress only that gesture's
        // click, never a new deliberate mouse/touch action.
        this.session.suppressClick = false;
        const hit = this.hit(event);
        if (!hit || !this.flushGPS()) return true;
        event.preventDefault?.();
        const snapshot = this.session.draft.vertices.map(coordinate => [...coordinate]);
        const index = Number(hit.properties.index);
        if (hit.properties.role === 'midpoint') {
            if (snapshot.length >= DEFAULTS.GIS_GEOMETRY.MAX_VERTICES) return true;
            this.session.draft.vertices.splice(index, 0, [...hit.geometry.coordinates]);
        }
        this.session.drawing = false;
        this.select(index);
        this.session.drag = { snapshot, start: pointFromEvent(event), moved: hit.properties.role === 'midpoint', panEnabled: this.map.dragPan?.isEnabled?.() ?? true };
        this.map.dragPan?.disable();
        this.render();
        return true;
    },

    handleMouseMove(event) {
        if (!this.session) return false;
        if (this.session.saving) return true;
        if (event.points?.length > 1) { this.cancelDrag(); return true; }
        const coordinates = coordinateFromEvent(event);
        const point = pointFromEvent(event);
        if (this.session.drag && coordinates) {
            const drag = this.session.drag;
            const distance = point && drag.start ? Math.hypot(point.x - drag.start.x, point.y - drag.start.y) : 0;
            if (distance >= DEFAULTS.GIS_GEOMETRY.DRAG_THRESHOLD) drag.moved = true;
            if (drag.moved) {
                this.session.draft.vertices[this.session.selected] = coordinates;
                this.nodes.latitude.value = String(coordinates[1]);
                this.nodes.longitude.value = String(coordinates[0]);
                this.session.error = '';
                this.render(false);
            }
            this.map.getCanvas().style.cursor = 'grabbing';
        } else {
            this.session.preview = this.session.drawing ? coordinates : null;
            this.map.getCanvas().style.cursor = this.hit(event) ? 'grab' : this.session.drawing ? 'crosshair' : '';
            this.renderMap();
        }
        return true;
    },

    handleMouseUp() {
        if (!this.session) return false;
        this.finishDrag();
        return true;
    },

    handleCancel() {
        if (!this.session) return false;
        this.cancelDrag();
        return true;
    },

    finishDrag() {
        if (!this.session?.drag) return;
        const { snapshot, moved, panEnabled } = this.session.drag;
        const final = this.session.draft.vertices.map(coordinate => [...coordinate]);
        this.session.draft.vertices = snapshot;
        if (moved) changeDraft(this.session.draft, final);
        this.session.suppressClick = moved;
        this.session.drag = null;
        if (panEnabled) this.map.dragPan?.enable();
        this.render();
    },

    cancelDrag() {
        if (!this.session?.drag) return;
        const { snapshot, panEnabled } = this.session.drag;
        this.session.draft.vertices = snapshot;
        this.session.drag = null;
        if (panEnabled) this.map.dragPan?.enable();
        this.select(null);
        this.render();
    },

    handleContextMenu(event) {
        if (!this.session) return false;
        event.preventDefault?.();
        return true;
    },

    handleKeyDown(event) {
        if (!this.session || this.session.saving) return;
        const typing = event.target instanceof Element && event.target.closest('input, textarea, select, [contenteditable="true"]');
        if (event.key === 'Escape') {
            event.preventDefault();
            if (this.session.drag) this.cancelDrag();
            else this.requestClose();
            return;
        }
        if (typing) return;
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
            event.preventDefault();
            this.performAction(event.shiftKey ? 'redo' : 'undo');
        } else if (event.key === 'Delete' || event.key === 'Backspace') {
            event.preventDefault();
            this.performAction('remove');
        } else if (event.key === 'Enter' && this.session.drawing
            && !(event.target instanceof Element && event.target.closest('button, a[href], summary, [role="button"]'))) {
            event.preventDefault();
            this.performAction('drawing');
        }
    },

    async save() {
        if (!this.session || this.session.saving || !this.flushGPS()) return false;
        this.finishDrag();
        const session = this.session;
        if (session.record && !this.hasUnsavedChanges()) return false;
        const geojson = geometryFromVertices(session.draft.type, session.draft.vertices);
        const validation = validateGeometry(geojson);
        if (!session.name.trim() || !validation.valid) {
            session.error = !session.name.trim() ? 'Enter a name for this geometry.' : validation.error;
            this.refreshUI();
            return false;
        }
        const payload = { name: session.name.trim(), color: session.color, geojson };
        if (session.record) payload.expected_revision = session.record.revision;
        session.saving = true;
        session.error = '';
        this.refreshUI();
        try {
            const record = session.record
                ? await API.updateGISGeometry(session.record.id, payload)
                : await API.createGISGeometry(payload);
            // Persistence succeeded even if the display callback fails. Never invite
            // a retry that would create a duplicate record after a rendering error.
            try {
                await this.onSaved(record);
            } catch {
                this.close(true);
                Utils.showNotification('error', 'Geometry saved, but the map could not refresh. Reload the viewer to see it.');
                return true;
            }
            this.close(true);
            Utils.showNotification('success', 'Geometry saved.');
            return true;
        } catch (error) {
            session.error = errorText(error);
            session.conflict = error.status === 409;
            session.saving = false;
            this.refreshUI();
            return false;
        }
    },

    requestClose(next = null) {
        if (!this.session || this.session.saving) return false;
        if (this.hasUnsavedChanges() || this.session.gpsDirty) {
            this.session.discardRequested = true;
            this.session.pendingAction = next;
            this.session.reloadRequested = false;
            this.nodes.discard.querySelector('p').textContent = 'Discard your unsaved changes?';
            this.nodes.discard.querySelector('[data-editor-action="discard"]').textContent = 'Discard changes';
            this.refreshUI();
            this.nodes.discard.querySelector('button')?.focus();
            return false;
        }
        this.close();
        return true;
    },

    close(force = false) {
        if (!this.session || (this.session.saving && !force)) return;
        this.cancelDrag();
        this.stopObservingViewport();
        const { record, returnFocus, doubleClickEnabled, pendingAction } = this.session;
        this.session = null;
        this.nodes?.root.remove();
        this.nodes = null;
        this.removeLayers();
        this.map.getCanvas().style.cursor = '';
        if (doubleClickEnabled) this.map.doubleClickZoom?.enable();
        this.onPreview(record?.id || null, false);
        if (!focusControl(returnFocus)) {
            const controls = document.querySelectorAll('#gis-geometries-panel-minimized, #gis-geometries-panel .gis-geometries-icon-button, #create-geometry-btn');
            [...controls].some(control => focusControl(control));
        }
        if (pendingAction && !force) void pendingAction();
    },

    refreshUI(refreshVertices = true) {
        const { session, nodes } = this;
        if (!session || !nodes) return;
        const validation = validateGeometry(this.prospectiveGeometry());
        const limits = DEFAULTS.GIS_GEOMETRY;
        const over = validation.areaM2 > limits.MAX_AREA_M2;
        const warning = validation.areaM2 > limits.WARNING_AREA_M2;
        nodes.root.classList.toggle('is-over-limit', over);
        nodes.root.classList.toggle('is-near-limit', warning && !over);
        nodes.areaValue.textContent = `${validation.areaKm2.toLocaleString(undefined, { maximumFractionDigits: limits.AREA_DISPLAY_PRECISION })} / ${limits.MAX_AREA_M2 / limits.SQUARE_METRES_PER_SQUARE_KILOMETRE} km²`;
        nodes.progressFill.style.width = `${Math.min(100, validation.areaM2 / limits.MAX_AREA_M2 * 100)}%`;
        const selected = session.selected !== null;
        nodes.hint.textContent = session.drawing
            ? 'Click to add points. Drag a point to adjust it, or enter GPS coordinates below.'
            : 'Drag a point to move it. Select a point to edit its GPS coordinates; select a midpoint to insert one.';
        nodes.gpsTitle.textContent = selected ? `Point ${session.selected + 1} · GPS coordinates` : 'Add GPS coordinates';
        nodes.apply.textContent = selected ? 'Update point' : 'Add point';
        nodes.apply.setAttribute('aria-label', nodes.apply.textContent);
        const message = session.error || (over ? `Over ${limits.MAX_AREA_M2 / limits.SQUARE_METRES_PER_SQUARE_KILOMETRE} km². Reduce the bounding box to keep the map responsive.`
            : !validation.valid ? validation.error : warning ? `Above ${limits.WARNING_AREA_M2 / limits.SQUARE_METRES_PER_SQUARE_KILOMETRE} km². The maximum is ${limits.MAX_AREA_M2 / limits.SQUARE_METRES_PER_SQUARE_KILOMETRE} km².` : `${validation.vertexCount} of ${limits.MAX_VERTICES} points · Ready to save`);
        if (nodes.status.textContent !== message) nodes.status.textContent = message;
        nodes.status.classList.toggle('has-error', Boolean(session.error) || over);
        for (const button of nodes.root.querySelectorAll('button')) button.disabled = session.saving;
        for (const input of nodes.root.querySelectorAll('input')) input.disabled = session.saving;
        nodes.save.disabled = session.saving || !session.name.trim() || !validation.valid || (Boolean(session.record) && !this.hasUnsavedChanges());
        nodes.save.textContent = session.saving ? 'Saving…' : 'Save geometry';
        nodes.discard.hidden = !session.discardRequested;
        nodes.conflict.hidden = !session.conflict;
        nodes.currentColor.style.backgroundColor = session.color;
        for (const button of nodes.types.children) {
            button.setAttribute('aria-pressed', String(button.dataset.type === session.draft.type));
            button.disabled = session.saving || Boolean(session.record) || session.draft.vertices.length > 0;
        }
        for (const button of nodes.colors.children) button.setAttribute('aria-pressed', String(button.dataset.color === session.color));
        const action = name => nodes.root.querySelector(`[data-editor-action="${name}"]`);
        action('undo').disabled = session.saving || !session.draft.undo.length;
        action('redo').disabled = session.saving || !session.draft.redo.length;
        action('remove').hidden = !selected;
        action('deselect').hidden = !selected;
        action('drawing').textContent = session.drawing ? 'Finish drawing' : 'Add points';
        action('drawing').disabled = session.saving || (!session.drawing && session.draft.vertices.length >= limits.MAX_VERTICES);
        action('deselect').disabled = session.saving || session.draft.vertices.length >= limits.MAX_VERTICES;
        nodes.apply.hidden = selected;
        nodes.apply.disabled = session.saving || (!selected && session.draft.vertices.length >= limits.MAX_VERTICES);
        if (refreshVertices) {
            const focusedAction = nodes.vertices.contains(document.activeElement)
                ? document.activeElement.dataset.editorAction : null;
            const count = session.draft.vertices.length;
            nodes.vertices.hidden = count === 0;
            const previous = this.button('previous', 'Previous point', '←');
            const next = this.button('next', 'Next point', '→');
            const choose = this.button('select', selected ? `Selected point ${session.selected + 1} of ${count}` : 'Select first point', selected ? `Point ${session.selected + 1} of ${count}` : `Edit ${count} ${count === 1 ? 'point' : 'points'}`);
            choose.dataset.index = String(session.selected ?? 0);
            previous.disabled = session.saving || !selected || session.selected === 0;
            next.disabled = session.saving || !selected || session.selected === count - 1;
            choose.disabled = session.saving;
            nodes.vertices.replaceChildren(previous, choose, next);
            if (focusedAction) {
                const replacement = nodes.vertices.querySelector(`[data-editor-action="${focusedAction}"]`);
                (replacement?.disabled ? choose : replacement)?.focus({ preventScroll: true });
            }
        }
    },

    render(refreshVertices = true) { this.renderMap(); this.refreshUI(refreshVertices); },

    restoreLayers() { if (this.session) this.renderMap(); },

    renderMap() {
        if (!this.session || !this.map.getStyle?.()) return;
        const { draft, color, selected, preview } = this.session;
        const geometry = geometryFromVertices(draft.type, draft.vertices);
        const validation = validateGeometry(geometry);
        const settings = DEFAULTS.GIS_GEOMETRY;
        const tone = validation.areaM2 > settings.MAX_AREA_M2 ? settings.COLORS.INVALID
            : validation.areaM2 > settings.WARNING_AREA_M2 ? settings.COLORS.WARNING : color;
        const features = [];
        if (draft.vertices.length >= 2) {
            const shape = draft.type === 'Polygon' && draft.vertices.length >= 3 ? geometry : { type: 'LineString', coordinates: draft.vertices };
            features.push(feature(shape, { role: 'shape', color: tone }));
        }
        if (preview && draft.vertices.length) {
            features.push(feature({ type: 'LineString', coordinates: [draft.vertices.at(-1), preview] }, { role: 'preview', color: tone }));
        }
        draft.vertices.forEach((coordinates, index) => {
            features.push(feature({ type: 'Point', coordinates }, { role: 'vertex', index, selected: selected === index, color }));
            const next = draft.vertices[index + 1] || (draft.type === 'Polygon' && draft.vertices.length >= 3 ? draft.vertices[0] : null);
            if (next && draft.vertices.length < settings.MAX_VERTICES) features.push(feature({ type: 'Point', coordinates: [(coordinates[0] + next[0]) / 2, (coordinates[1] + next[1]) / 2] }, { role: 'midpoint', index: index + 1, color }));
        });
        if (validation.bounds && draft.vertices.length > 1) {
            const [[west, south], [east, north]] = validation.bounds;
            features.push(feature({ type: 'LineString', coordinates: [[west, south], [east, south], [east, north], [west, north], [west, south]] }, { role: 'bbox', color: tone }));
        }
        const data = { type: 'FeatureCollection', features };
        if (this.map.getSource(SOURCE)) { this.map.getSource(SOURCE).setData(data); return; }
        this.map.addSource(SOURCE, { type: 'geojson', data });
        this.map.addLayer({ id: LAYERS[0], type: 'fill', source: SOURCE, filter: ['==', '$type', 'Polygon'], paint: { 'fill-color': ['get', 'color'], 'fill-opacity': settings.DRAFT_FILL_OPACITY } });
        this.map.addLayer({ id: LAYERS[1], type: 'line', source: SOURCE, filter: ['in', 'role', 'shape', 'preview'], paint: { 'line-color': ['get', 'color'], 'line-width': settings.LINE_WIDTH } });
        this.map.addLayer({ id: LAYERS[2], type: 'line', source: SOURCE, filter: ['==', 'role', 'bbox'], paint: { 'line-color': ['get', 'color'], 'line-width': settings.BBOX_LINE_WIDTH, 'line-dasharray': settings.BBOX_DASH_ARRAY } });
        this.map.addLayer({ id: LAYERS[3], type: 'circle', source: SOURCE, filter: ['==', 'role', 'midpoint'], paint: { 'circle-radius': settings.MIDPOINT_RADIUS, 'circle-color': settings.COLORS.HANDLE, 'circle-stroke-color': ['get', 'color'], 'circle-stroke-width': settings.VERTEX_STROKE_WIDTH } });
        this.map.addLayer({ id: LAYERS[4], type: 'circle', source: SOURCE, filter: ['==', 'role', 'vertex'], paint: { 'circle-radius': ['case', ['get', 'selected'], settings.SELECTED_VERTEX_RADIUS, settings.VERTEX_RADIUS], 'circle-color': ['case', ['get', 'selected'], settings.COLORS.SELECTED, settings.COLORS.HANDLE], 'circle-stroke-color': ['get', 'color'], 'circle-stroke-width': settings.VERTEX_STROKE_WIDTH } });
    },

    removeLayers() {
        if (!this.map) return;
        [...LAYERS].reverse().forEach(id => { if (this.map.getLayer(id)) this.map.removeLayer(id); });
        if (this.map.getSource(SOURCE)) this.map.removeSource(SOURCE);
    },

    destroy() {
        if (this.session) this.close(true);
        this.stopObservingViewport();
        if (this._keyHandler) document.removeEventListener('keydown', this._keyHandler);
        if (this._leaveHandler) window.removeEventListener('beforeunload', this._leaveHandler);
        if (this._outsideUp) { window.removeEventListener('mouseup', this._outsideUp); window.removeEventListener('touchend', this._outsideUp); }
        if (this._cancelDrag) { window.removeEventListener('touchcancel', this._cancelDrag); window.removeEventListener('blur', this._cancelDrag); }
        if (this._doubleClick) this.map?.off?.('dblclick', this._doubleClick);
    },
};
