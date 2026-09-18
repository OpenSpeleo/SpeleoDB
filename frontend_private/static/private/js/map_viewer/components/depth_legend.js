import { State } from '../state.js';
import { DEFAULTS } from '../config.js';
import { depthFromFeet, isValidDepthLimit } from '../map/depth.js';
import { Layers } from '../map/layers.js';

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function getNumeric(value) {
    if (value === null || value === undefined || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
}

function getDepthUnit() {
    return State.displayPreferences.depthUnit === 'm' ? 'm' : 'ft';
}

function getDepthLimit() {
    const limit = State.displayPreferences.depthLimitFeet;
    return isValidDepthLimit(limit) ? limit : null;
}

function formatExactDepth(feet, unit) {
    return String(Number(depthFromFeet(feet, unit).toPrecision(DEFAULTS.DEPTH.INPUT_SIGNIFICANT_DIGITS)));
}

export const DepthLegend = {
    map: null,
    colorMode: 'project',
    depthDomain: null,
    initialized: false,
    onColorModeChangedHandler: null,
    onDepthDomainUpdatedHandler: null,
    onMapMouseMoveHandler: null,
    onMapMouseOutHandler: null,
    hoveredLineFeature: null,

    init: function (map) {
        if (!map || this.initialized) return;

        this.map = map;
        this.colorMode = State.displayPreferences.colorMode;
        this.depthDomain = State.activeDepthDomain;
        this.initialized = true;

        this.onColorModeChangedHandler = (event) => {
            this.colorMode = event?.detail?.mode === 'depth' ? 'depth' : 'project';
            this.updateDepthLegendVisibility();
            if (this.colorMode !== 'depth') {
                this.hideDepthCursor();
            }
        };

        this.onDepthDomainUpdatedHandler = (event) => {
            const domain = event?.detail?.domain;
            if (domain && Number.isFinite(domain.max)) {
                this.depthDomain = { min: 0, max: Math.max(0, domain.max) };
            } else {
                const max = getNumeric(event?.detail?.max);
                this.depthDomain = Number.isFinite(max) ? { min: 0, max: Math.max(0, max) } : null;
            }

            this.createOrUpdateDepthScale();
            this.updateDepthLegendVisibility();
            this.renderDepthCursor();
        };

        this.onMapMouseMoveHandler = (event) => {
            this.updateDepthCursor(event);
        };
        this.onMapMouseOutHandler = () => this.hideDepthCursor();

        window.addEventListener('speleo:color-mode-changed', this.onColorModeChangedHandler);
        window.addEventListener('speleo:depth-domain-updated', this.onDepthDomainUpdatedHandler);

        this.map.on('mousemove', this.onMapMouseMoveHandler);
        this.map.on('mouseout', this.onMapMouseOutHandler);
        this.createOrUpdateDepthScale();
        this.updateDepthLegendVisibility();
    },

    destroy: function () {
        if (!this.initialized) return;

        window.removeEventListener('speleo:color-mode-changed', this.onColorModeChangedHandler);
        window.removeEventListener('speleo:depth-domain-updated', this.onDepthDomainUpdatedHandler);

        if (this.map && typeof this.map.off === 'function') {
            this.map.off('mousemove', this.onMapMouseMoveHandler);
            this.map.off('mouseout', this.onMapMouseOutHandler);
        }

        this.map = null;
        this.colorMode = 'project';
        this.depthDomain = null;
        this.initialized = false;
        this.onColorModeChangedHandler = null;
        this.onDepthDomainUpdatedHandler = null;
        this.onMapMouseMoveHandler = null;
        this.onMapMouseOutHandler = null;
        this.hoveredLineFeature = null;
    },

    createOrUpdateDepthScale: function () {
        try {
            const mapContainer = document.getElementById('map');
            if (!mapContainer) return;

            let container = document.getElementById('depth-scale-fixed');
            if (!container) {
                container = document.createElement('div');
                container.id = 'depth-scale-fixed';
                container.style.position = 'absolute';
                container.style.left = '5px';
                container.style.bottom = '5px';
                container.style.zIndex = '5';
                container.style.backgroundColor = '#0f172a';
                container.style.border = '2px solid #475569';
                container.style.borderRadius = '8px';
                container.style.padding = '8px 10px';
                mapContainer.appendChild(container);
            }

            const hasDomain = this.depthDomain && Number.isFinite(this.depthDomain.max);
            const unit = getDepthUnit();
            const maximum = hasDomain
                ? (unit === 'ft' && getDepthLimit() === null
                    ? Math.ceil(this.depthDomain.max)
                    : formatExactDepth(this.depthDomain.max, unit))
                : null;
            const minLabel = hasDomain ? `0 ${unit}` : 'N/A';
            const maxLabel = hasDomain ? `${maximum} ${unit}` : 'N/A';

            container.innerHTML = `
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="color:#94a3b8; font-size:12px;">Depth</span>
                    <div id="depth-scale-gradient" style="position:relative; width:160px; height:10px; background: linear-gradient(90deg, #4575b4 0%, #e6f598 50%, #d73027 100%); border-radius: 4px;">
                        <div id="depth-cursor-indicator" style="position:absolute; top:-3px; left:0; width:2px; height:16px; background:#ffffff; box-shadow:0 0 4px rgba(0,0,0,0.6); display:none; transition:left 0.15s ease-out;"></div>
                        <div id="depth-cursor-label" style="position:absolute; top:-27px; left:0; transform:translateX(-50%); color:#e5e7eb; font-size:13px; background: rgba(2, 6, 23, 0.9); border: 1px solid #334155; padding: 2px 6px; border-radius: 3px; display:none; pointer-events:none; white-space:nowrap; transition:left 0.15s ease-out;"></div>
                    </div>
                </div>
                <div style="display:flex; justify-content:space-between; color:#94a3b8; font-size:11px; margin-top:4px;">
                    <span>${minLabel}</span>
                    <span>${maxLabel}</span>
                </div>
            `;
        } catch (e) {
            console.warn('Unable to render/update depth scale:', e);
        }
    },

    updateDepthLegendVisibility: function () {
        try {
            const depthLegend = document.getElementById('depth-scale-fixed');
            if (!depthLegend) return;
            const shouldShow = this.colorMode === 'depth';
            depthLegend.style.display = shouldShow ? 'block' : 'none';
            if (!shouldShow) {
                this.hideDepthCursor();
            }
        } catch (e) {
            // Ignore visual update errors.
        }
    },

    hideDepthCursor: function () {
        this.hoveredLineFeature = null;
        const indicator = document.getElementById('depth-cursor-indicator');
        const label = document.getElementById('depth-cursor-label');
        if (indicator) indicator.style.display = 'none';
        if (label) label.style.display = 'none';
    },

    updateDepthCursor: function (event) {
        if (this.colorMode !== 'depth' || !this.depthDomain || !Number.isFinite(this.depthDomain.max)) {
            this.hideDepthCursor();
            return;
        }

        const queryPaddingPx = DEFAULTS.DEPTH.HOVER_QUERY_PADDING_PX;
        const queryBox = [
            [event.point.x - queryPaddingPx, event.point.y - queryPaddingPx],
            [event.point.x + queryPaddingPx, event.point.y + queryPaddingPx]
        ];

        let features = [];
        try {
            features = this.map.queryRenderedFeatures(queryBox);
        } catch (err) {
            features = [];
        }

        const lineFeature = features.find((feature) =>
            feature?.layer?.type === 'line' &&
            feature?.properties &&
            (feature.properties.depth_val !== undefined || feature.properties.depth_norm !== undefined)
        );

        this.hoveredLineFeature = lineFeature || null;
        this.renderDepthCursor();
    },

    renderDepthCursor() {
        const lineFeature = this.hoveredLineFeature;
        if (this.colorMode !== 'depth' || !this.depthDomain || !lineFeature) {
            this.hideDepthCursor();
            return;
        }

        const indicator = document.getElementById('depth-cursor-indicator');
        const labelEl = document.getElementById('depth-cursor-label');
        if (!indicator || !labelEl) return;

        const sourceId = lineFeature.source || lineFeature.layer?.source;
        const projectId = typeof sourceId === 'string' && sourceId.startsWith('project-geojson-')
            ? sourceId.slice('project-geojson-'.length) : null;
        if (projectId && (!State.projectDepthDomains.has(projectId) || !Layers.isProjectEffectivelyVisible(projectId))) {
            this.hideDepthCursor();
            return;
        }

        const props = lineFeature.properties || {};
        const maxDepth = this.depthDomain.max > 0
            ? this.depthDomain.max : DEFAULTS.DEPTH.ZERO_DOMAIN_MAX_FEET;
        const rawDepth = getNumeric(props.depth_val);
        const rawNorm = getNumeric(props.depth_norm);

        if (Number.isFinite(rawDepth)) {
            this.showDepthCursor(rawDepth, maxDepth, indicator, labelEl);
            return;
        }

        if (Number.isFinite(rawNorm)) {
            const clampedNorm = clamp(rawNorm, 0, 1);
            // Legacy normalized values refer to the source project's uncapped scale.
            const projectDomain = projectId ? State.projectDepthDomains.get(projectId) : null;
            const sourceMax = getDepthLimit() !== null && Number.isFinite(projectDomain?.max)
                ? projectDomain.max : maxDepth;
            this.showDepthCursor(clampedNorm * sourceMax, maxDepth, indicator, labelEl);
            return;
        }

        this.hideDepthCursor();
    },

    showDepthCursor(rawDepth, maxDepth, indicator, labelEl) {
        const limit = getDepthLimit();
        const unit = getDepthUnit();
        const depth = limit === null ? rawDepth : Math.min(rawDepth, limit);
        const pct = clamp(depth / maxDepth, 0, 1) * 100;
        const rounded = depthFromFeet(depth, unit).toFixed(DEFAULTS.DEPTH.DISPLAY_DECIMALS);
        const roundedPastLimit = limit !== null && Number(rounded) > depthFromFeet(limit, unit);
        const label = limit !== null && (rawDepth >= limit || roundedPastLimit)
            ? formatExactDepth(limit, unit) : rounded;
        indicator.style.left = `calc(${pct}% - 1px)`;
        indicator.style.display = 'block';
        labelEl.textContent = `${label} ${unit}`;
        labelEl.style.left = `calc(${pct}% - 0px)`;
        labelEl.style.display = 'block';
    }
};
