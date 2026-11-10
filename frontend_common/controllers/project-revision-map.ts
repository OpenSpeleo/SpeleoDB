import { initRevisionPlayback } from './revision-playback.ts';
import type { ProjectRevisionMapContext } from '../../ts-types/controllers/project-revision-map.ts';
import { configureRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';
import { DEFAULTS } from '../../frontend_private/static/private/ts/map_viewer/defaults.ts';
import { State } from '../../frontend_private/static/private/ts/map_viewer/state.ts';
import { computeCameraPadding } from '@speleodb/map-viewer/camera-padding';

export async function init(context: ProjectRevisionMapContext) {
    configureRuntimeContext({ mapboxToken: context.mapboxToken });
    const { initReadOnlyViewer } = await import(
        '../../frontend_private/static/private/ts/map_viewer/read_only_viewer.ts'
    );
    const { MapSettings } = await import('../../frontend_private/static/private/ts/map_viewer/components/settings.ts');
    const fullscreenContainer = document.getElementById('map-viewer-shell');
    fullscreenContainer?.style.setProperty('--revision-scale-width', `${DEFAULTS.HISTORY.SCALE_CONTROL_MAX_WIDTH}px`);
    const dock = document.getElementById('revision-timeline');
    const mapElement = document.getElementById('map');
    const panel = document.querySelector<HTMLDetailsElement>('.historical-revisions');
    const playbackMetadata = document.getElementById('revision-playback-metadata');
    const bottomControls = '.maplibregl-ctrl-bottom-left, .maplibregl-ctrl-bottom-right';
    const viewer = await initReadOnlyViewer(context, async () => ({
        view_name: context.project.name,
        projects: [context.project],
    }), {
        showProjectPanel: false,
        showDepthLegend: false,
        showAttribution: false,
        scaleControlMaxWidth: DEFAULTS.HISTORY.SCALE_CONTROL_MAX_WIDTH,
        ...(fullscreenContainer ? { fullscreenContainer } : {}),
        cameraPadding: () => {
            const margin = DEFAULTS.HISTORY.CAMERA_PADDING_PX;
            const bounds = mapElement?.getBoundingClientRect();
            if (!bounds) return margin;
            const overlays = [
                dock,
                panel,
                playbackMetadata,
                mapElement?.querySelector<HTMLElement>('.maplibregl-ctrl-top-right'),
                ...(mapElement?.querySelectorAll<HTMLElement>(bottomControls) ?? []),
            ];
            return computeCameraPadding(bounds, {
                left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight,
            }, {
                padding: margin,
                marginRatio: DEFAULTS.HISTORY.CAMERA_MARGIN_RATIO,
                obstacles: overlays.filter((element): element is HTMLElement => !!element && !element.hidden && !!element.getClientRects().length)
                    .map(element => element.getBoundingClientRect()),
            });
        },
    });
    MapSettings.init({ surveyOnly: true });
    const playback = initRevisionPlayback(context, viewer);
    const map = State.map;
    const destroy = () => {
        playback.destroy();
        map?.off('remove', destroy);
        window.removeEventListener('pagehide', pageHidden);
    };
    const pageHidden = (event: PageTransitionEvent) => {
        if (!event.persisted) destroy();
    };
    map?.on('remove', destroy);
    window.addEventListener('pagehide', pageHidden);
}
