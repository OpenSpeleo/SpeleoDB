import { DEFAULTS } from '../config.js';
import { createMeasurement, measurementFeatures } from './geometry.js';

const settings = DEFAULTS.MEASUREMENT;
export const MEASUREMENT_LAYER_PREFIX = settings.LAYER_PREFIX;
const imageId = `${MEASUREMENT_LAYER_PREFIX}capsule`;
const sourceId = kind => `${MEASUREMENT_LAYER_PREFIX}${kind}`;
const collection = features => ({ type: 'FeatureCollection', features });
const rgba = ([red, green, blue, alpha]) => `rgba(${red}, ${green}, ${blue}, ${alpha / 255})`;

function styleReady(map) {
    try {
        // Unlike isStyleLoaded(), serialization waits only for the style itself,
        // not all outstanding basemap tiles. It is never called per draft frame.
        return Boolean(map.getStyle());
    } catch (error) {
        if (error.message === 'Style is not done loading') return false;
        throw error;
    }
}

/** Raw pixels avoid asynchronous image loading and remain usable after style reloads. */
function capsuleImage() {
    const size = settings.LABEL_IMAGE_SIZE;
    const radius = settings.LABEL_IMAGE_RADIUS;
    const data = new Uint8Array(size * size * 4);
    for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
            const centerX = Math.max(radius, Math.min(size - radius, x));
            const centerY = Math.max(radius, Math.min(size - radius, y));
            const edge = Math.max(Math.hypot(x - centerX, y - centerY) - radius,
                -x, -y, x - size + 1, y - size + 1);
            if (edge > 0) continue;
            const rgba = edge > -settings.LABEL_IMAGE_BORDER_WIDTH
                ? settings.LABEL_BORDER_RGBA : settings.LABEL_BACKGROUND_RGBA;
            data.set(rgba, (y * size + x) * 4);
        }
    }
    return { width: size, height: size, data };
}

function layersFor(kind) {
    const source = sourceId(kind);
    const lineFilter = ['==', ['get', 'role'], 'line'];
    const linePaint = { 'line-color': settings.LINE_COLOR, 'line-width': settings.LINE_WIDTH };
    if (kind === 'draft') linePaint['line-dasharray'] = settings.DRAFT_DASH_ARRAY;
    const layers = [
        {
            id: `${source}-casing`, type: 'line', source, filter: lineFilter,
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': settings.CASING_COLOR, 'line-width': settings.CASING_WIDTH },
        },
        {
            id: `${source}-line`, type: 'line', source, filter: lineFilter,
            layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: linePaint,
        },
        {
            id: `${source}-endpoints`, type: 'circle', source, filter: ['==', ['get', 'role'], 'endpoint'],
            paint: {
                'circle-radius': settings.ENDPOINT_RADIUS, 'circle-color': settings.CASING_COLOR,
                'circle-stroke-color': settings.LINE_COLOR, 'circle-stroke-width': settings.ENDPOINT_STROKE_WIDTH,
            },
        },
    ];
    if (kind === 'completed') layers.push({
            id: `${source}-label`, type: 'symbol', source, filter: ['==', ['get', 'role'], 'label'],
            layout: {
                'symbol-sort-key': ['get', 'priority'],
                'text-field': ['get', 'label'], 'text-font': settings.LABEL_FONTS,
                'text-size': settings.LABEL_TEXT_SIZE, 'text-variable-anchor': settings.LABEL_ANCHORS,
                'text-padding': settings.LABEL_COLLISION_PADDING,
                'text-allow-overlap': false, 'text-ignore-placement': false,
                'icon-image': imageId, 'icon-text-fit': 'both',
                'icon-text-fit-padding': settings.LABEL_PADDING,
                'icon-allow-overlap': false, 'icon-ignore-placement': false,
                'icon-optional': false, 'text-optional': false,
                'icon-pitch-alignment': 'viewport', 'text-pitch-alignment': 'viewport',
                'icon-rotation-alignment': 'viewport', 'text-rotation-alignment': 'viewport',
            },
            paint: { 'text-color': settings.LABEL_TEXT_COLOR },
        });
    return layers;
}

/** Owns only measurement overlays; completed geometry is never rebuilt on pointer movement. */
export class MeasurementRenderer {
    constructor(map) {
        this.map = map;
        this.active = false;
        this.destroyed = false;
        this.draft = null;
        this.draftFrame = null;
        this.liveMarker = null;
        this.liveLabel = null;
        this.completedData = collection([]);
        this.draftData = collection([]);
        this.completedFeatures = new WeakMap();
        this.restoreHandler = () => this.restore();
        map.on('style.load', this.restoreHandler);
    }

    setMeasurements(records) {
        if (this.destroyed) return;
        this.active = true;
        this.completedData = collection(records.flatMap((record, index) => {
            const priority = 0 - index;
            let cached = this.completedFeatures.get(record);
            if (!cached) {
                cached = { priority, features: measurementFeatures(record, priority) };
                this.completedFeatures.set(record, cached);
            } else if (cached.priority !== priority) {
                cached = { priority, features: cached.features.map(feature => ({ ...feature, properties: { ...feature.properties, priority } })) };
                this.completedFeatures.set(record, cached);
            }
            return cached.features;
        }));
        if (!this.map.getSource(sourceId('completed'))) this.ensureOverlays();
        this.map.getSource(sourceId('completed'))?.setData(this.completedData);
    }

    setDraft(draft) {
        if (this.destroyed) return;
        this.active = true;
        this.draft = draft ? { start: [...draft.start], end: draft.end ? [...draft.end] : null } : null;
        if (!this.draft?.end) this.removeLiveLabel();
        if (this.draftFrame !== null) return;
        this.draftFrame = requestAnimationFrame(() => {
            this.draftFrame = null;
            if (!this.active || this.destroyed) return;
            const record = this.draft?.end
                ? createMeasurement(this.draft.start, this.draft.end, 'draft')
                : this.draft;
            this.draftData = collection(record ? measurementFeatures(record) : []);
            this.updateLiveLabel(this.draftData.features.find(feature => feature.properties.role === 'label'));
            if (!this.map.getSource(sourceId('draft'))) this.ensureOverlays();
            this.map.getSource(sourceId('draft'))?.setData(this.draftData);
        });
    }

    updateLiveLabel(feature) {
        if (!feature) {
            this.removeLiveLabel();
            return;
        }
        if (!this.liveMarker) {
            this.liveLabel = document.createElement('div');
            this.liveLabel.className = 'measurement-live-label';
            this.liveLabel.setAttribute('aria-hidden', 'true');
            const variables = {
                'font-size': `${settings.LABEL_TEXT_SIZE}px`,
                padding: settings.LABEL_PADDING.map(value => `${value}px`).join(' '),
                background: rgba(settings.LABEL_BACKGROUND_RGBA),
                color: settings.LABEL_TEXT_COLOR,
                'border-color': rgba(settings.LABEL_BORDER_RGBA),
                'border-width': `${settings.LABEL_IMAGE_BORDER_WIDTH}px`,
                radius: `${settings.LABEL_IMAGE_RADIUS}px`,
            };
            for (const [name, value] of Object.entries(variables)) {
                this.liveLabel.style.setProperty(`--measurement-label-${name}`, value);
            }
            // One live Marker bypasses symbol-placement fading when numeric text
            // changes continuously. Mapbox still owns projection and occlusion.
            this.liveMarker = new mapboxgl.Marker({
                element: this.liveLabel, anchor: 'center',
                occludedOpacity: settings.LIVE_LABEL_OCCLUDED_OPACITY,
            }).setLngLat(feature.geometry.coordinates).addTo(this.map);
        } else {
            this.liveMarker.setLngLat(feature.geometry.coordinates);
        }
        this.liveLabel.textContent = feature.properties.label;
    }

    removeLiveLabel() {
        this.liveMarker?.remove();
        this.liveMarker = null;
        this.liveLabel = null;
    }

    ensureOverlays() {
        if (!this.active || this.destroyed || !styleReady(this.map)) return;
        if (!this.map.hasImage(imageId)) {
            const size = settings.LABEL_IMAGE_SIZE;
            const radius = settings.LABEL_IMAGE_RADIUS;
            this.map.addImage(imageId, capsuleImage(), {
                stretchX: [[radius, size - radius]], stretchY: [[radius, size - radius]],
                // Text-fit padding owns the inset; another content inset would
                // add the fixed corner width twice and make the capsule bulky.
                content: [0, 0, size, size],
            });
        }
        for (const kind of ['completed', 'draft']) {
            const data = kind === 'completed' ? this.completedData : this.draftData;
            if (!this.map.getSource(sourceId(kind))) this.map.addSource(sourceId(kind), { type: 'geojson', data });
            for (const layer of layersFor(kind)) {
                if (!this.map.getLayer(layer.id)) this.map.addLayer(layer);
            }
        }
    }

    restore() {
        if (!this.active || this.destroyed) return;
        if (this.map.getSource(sourceId('completed')) && this.map.getSource(sourceId('draft'))) return;
        this.ensureOverlays();
    }

    clear() {
        this.active = false;
        this.draft = null;
        this.removeLiveLabel();
        if (this.draftFrame !== null) cancelAnimationFrame(this.draftFrame);
        this.draftFrame = null;
        this.completedData = collection([]);
        this.draftData = collection([]);
        this.completedFeatures = new WeakMap();
        if (!styleReady(this.map)) return;
        for (const role of [...settings.LAYER_ROLES].reverse()) {
            const id = `${MEASUREMENT_LAYER_PREFIX}${role}`;
            if (this.map.getLayer(id)) this.map.removeLayer(id);
        }
        for (const kind of ['completed', 'draft']) {
            if (this.map.getSource(sourceId(kind))) this.map.removeSource(sourceId(kind));
        }
        if (this.map.hasImage(imageId)) this.map.removeImage(imageId);
    }

    destroy() {
        if (this.destroyed) return;
        this.clear();
        this.destroyed = true;
        this.map.off('style.load', this.restoreHandler);
    }
}
