import type { ProjectRevisionMapContext } from '../../ts-types/controllers/project-revision-map.ts';
import { configureRuntimeContext } from '../../frontend_private/static/private/ts/map_viewer/runtime_context.ts';

export async function init(context: ProjectRevisionMapContext) {
    configureRuntimeContext({ mapboxToken: context.mapboxToken });
    const { initReadOnlyViewer } = await import(
        '../../frontend_private/static/private/ts/map_viewer/read_only_viewer.ts'
    );
    const { MapSettings } = await import('../../frontend_private/static/private/ts/map_viewer/components/settings.ts');
    const fullscreenContainer = document.getElementById('map-viewer-shell');
    const viewer = await initReadOnlyViewer(context, async () => ({
        view_name: context.project.name,
        projects: [context.project],
    }), { showProjectPanel: false, ...(fullscreenContainer ? { fullscreenContainer } : {}) });
    MapSettings.init({ surveyOnly: true });

    const list = document.querySelector<HTMLElement>('.historical-revision-list');
    const status = document.querySelector<HTMLElement>('.historical-revision-status');
    let selected = list?.querySelector<HTMLAnchorElement>('a[aria-current="page"]') ?? null;
    let pending: object | null = null;
    selected?.scrollIntoView({ block: 'nearest' });

    async function selectRevision(link: HTMLAnchorElement, pushHistory: boolean) {
        const geojsonUrl = link.dataset.geojsonUrl;
        if (!geojsonUrl || (selected === link && !pending)) return;
        const selection = {};
        pending = selection;
        list?.setAttribute('aria-busy', 'true');
        if (status) status.textContent = 'Loading revision…';
        try {
            const displayed = await viewer.showProject({ ...context.project, geojson_file: geojsonUrl });
            if (pending !== selection) return;
            if (!displayed) {
                if (status) status.textContent = 'Unable to load this revision. Select it to try again.';
                if (!pushHistory && selected) history.replaceState(null, '', selected.href);
                return;
            }
            selected?.classList.remove('is-selected');
            selected?.removeAttribute('aria-current');
            selected = link;
            link.classList.add('is-selected');
            link.setAttribute('aria-current', 'page');
            if (pushHistory) history.pushState(null, '', link.href);
            link.scrollIntoView({ block: 'nearest' });
            if (status) status.textContent = '';
        } catch (error) {
            if (pending !== selection) return;
            console.error('Failed to select historical revision', error);
            if (status) status.textContent = 'Unable to load this revision. Select it to try again.';
            if (!pushHistory && selected) history.replaceState(null, '', selected.href);
        } finally {
            if (pending === selection) {
                pending = null;
                list?.removeAttribute('aria-busy');
            }
        }
    }

    list?.addEventListener('click', event => {
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const link = event.target instanceof Element
            ? event.target.closest<HTMLAnchorElement>('a.historical-revision') : null;
        if (!link || !list.contains(link) || !link.dataset.geojsonUrl) return;
        event.preventDefault();
        void selectRevision(link, true);
    });
    window.addEventListener('popstate', () => {
        const link = [...list?.querySelectorAll<HTMLAnchorElement>('a.historical-revision') ?? []]
            .find(item => new URL(item.href).pathname.toLowerCase() === location.pathname.toLowerCase());
        if (link) void selectRevision(link, false);
    });
}
