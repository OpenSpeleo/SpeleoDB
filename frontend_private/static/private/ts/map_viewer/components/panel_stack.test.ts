import { registerMapPanel, setMapPanelExpanded, unregisterMapPanel } from './panel_stack.ts';

const panels = [
    { id: 'project-panel', title: 'Active Projects' },
    { id: 'gis-geometries-panel', title: 'GIS Geometries' },
    { id: 'gis-layers-panel', title: 'GIS Layers' },
    { id: 'gps-tracks-panel', title: 'GPS Tracks' },
];

function createPanel(id: string, title: string, expanded = false) {
    const panel = document.createElement('section');
    panel.id = id;
    const heading = document.createElement('h3');
    heading.textContent = title;
    const collapse = document.createElement('button');
    collapse.id = `${id}-collapse`;
    collapse.textContent = `Minimize ${title}`;
    const control = document.createElement('input');
    control.type = 'checkbox';
    panel.append(heading, collapse, control);
    const minimized = document.createElement('div');
    minimized.id = `${id}-minimized`;
    const expand = document.createElement('button');
    expand.id = `${id}-expand`;
    expand.textContent = `Expand ${title}`;
    minimized.append(expand);
    document.body.append(panel, minimized);
    registerMapPanel(id, expand.id, collapse.id, expanded);
    return { panel, minimized, expand, collapse, control };
}

beforeEach(() => {
    document.body.innerHTML = '<div id="map"></div><button id="outside">Outside</button>';
});

afterEach(() => {
    for (const { id } of panels) unregisterMapPanel(id);
    document.body.replaceChildren();
});

it('inserts panels alphabetically regardless of registration order inside the fullscreen map', () => {
    for (const { id, title } of [...panels].reverse()) createPanel(id, title, id === 'project-panel');

    const stack = document.querySelector<HTMLElement>('#map > #map-panel-stack')!;
    expect(stack).not.toBeNull();
    expect([...stack.querySelectorAll('h3')].map(heading => heading.textContent))
        .toEqual(panels.map(panel => panel.title));
    expect(stack.querySelectorAll('.map-panel-slot')).toHaveLength(panels.length);
    expect([...stack.querySelectorAll<HTMLElement>('section')].filter(panel => !panel.hidden).map(panel => panel.id))
        .toEqual(['project-panel']);
});

it('opens only the selected panel and allows every panel to be collapsed', () => {
    const controls = panels.map(({ id, title }) => createPanel(id, title, id === 'project-panel'));
    controls[0]!.control.checked = true;

    for (const current of controls) {
        current.expand.click();
        for (const candidate of controls) {
            const expanded = candidate === current;
            expect(candidate.panel.hidden).toBe(!expanded);
            expect(candidate.minimized.hidden).toBe(expanded);
            expect(candidate.expand.getAttribute('aria-expanded')).toBe(String(expanded));
            expect(candidate.collapse.getAttribute('aria-expanded')).toBe(String(expanded));
        }
    }

    controls.at(-1)!.collapse.click();
    expect(controls.every(({ panel, minimized }) => panel.hidden && !minimized.hidden)).toBe(true);
    expect(controls[0]!.control.checked).toBe(true);
});

it('moves keyboard focus to the visible control without letting a closed sibling steal it', () => {
    const project = createPanel('project-panel', 'Active Projects', true);
    const geometry = createPanel('gis-geometries-panel', 'GIS Geometries');
    geometry.expand.focus();
    geometry.expand.click();
    expect(project.panel.hidden).toBe(true);
    expect(document.activeElement).toBe(geometry.collapse);

    geometry.control.focus();
    setMapPanelExpanded('gis-geometries-panel', false);
    expect(document.activeElement).toBe(geometry.expand);

    const outside = document.getElementById('outside')!;
    outside.focus();
    setMapPanelExpanded('project-panel', true);
    expect(document.activeElement).toBe(outside);
});

it('reregisters the same panel without duplicate slots or click transitions', () => {
    const project = createPanel('project-panel', 'Active Projects', true);
    const geometry = createPanel('gis-geometries-panel', 'GIS Geometries');
    registerMapPanel('gis-geometries-panel', geometry.expand.id, geometry.collapse.id);
    registerMapPanel('project-panel', project.expand.id, project.collapse.id, true);

    expect(document.querySelectorAll('#map-panel-stack')).toHaveLength(1);
    expect(document.querySelectorAll('.map-panel-slot')).toHaveLength(2);
    geometry.expand.click();
    expect(geometry.panel.hidden).toBe(false);
    expect(project.panel.hidden).toBe(true);
    geometry.collapse.click();
    expect(geometry.panel.hidden).toBe(true);
    expect(geometry.minimized.hidden).toBe(false);
});

it('supports an expand button that is itself the minimized card', () => {
    const panel = document.createElement('section');
    panel.id = 'gis-geometries-panel';
    panel.innerHTML = '<h3>GIS Geometries</h3><button id="geometry-collapse">Minimize</button>';
    const minimized = document.createElement('button');
    minimized.id = 'gis-geometries-panel-minimized';
    minimized.textContent = 'GIS Geometries';
    document.body.append(panel, minimized);

    registerMapPanel(panel.id, minimized.id, 'geometry-collapse');
    minimized.focus();
    minimized.click();
    expect(panel.hidden).toBe(false);
    expect(minimized.hidden).toBe(true);
    expect(document.activeElement?.id).toBe('geometry-collapse');
});

it('removes only the unregistered panel and accepts absent panel operations', () => {
    const project = createPanel('project-panel', 'Active Projects', true);
    const geometry = createPanel('gis-geometries-panel', 'GIS Geometries');
    unregisterMapPanel('gis-geometries-panel');
    expect(geometry.panel.isConnected).toBe(false);
    expect(geometry.minimized.isConnected).toBe(false);
    expect(project.panel.isConnected).toBe(true);
    expect(document.querySelectorAll('.map-panel-slot')).toHaveLength(1);

    expect(() => setMapPanelExpanded('gis-layers-panel', true)).not.toThrow();
    expect(() => unregisterMapPanel('gis-layers-panel')).not.toThrow();
    expect(() => registerMapPanel('gis-layers-panel', 'missing-expand', 'missing-collapse')).not.toThrow();
    expect(document.querySelectorAll('.map-panel-slot')).toHaveLength(1);
});
