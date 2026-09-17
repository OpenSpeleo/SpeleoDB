import { init } from './private-navigation.js';

afterEach(() => {
    document.body.innerHTML = '';
});

it('keeps GIS Tooling closed on unrelated pages, even if another link is current', () => {
    document.body.innerHTML = `
        <a href="/map/" aria-current="page">GIS Survey Map</a>
        <details id="gis-tooling"><summary>GIS Tooling</summary>
            <a href="/layers/">GIS Layers</a>
        </details>`;
    init();
    expect(document.getElementById('gis-tooling').open).toBe(false);
});

it('opens GIS Tooling for its current page and permits a manual collapse', () => {
    document.body.innerHTML = `
        <details id="gis-tooling"><summary>GIS Tooling</summary>
            <a href="/layers/" aria-current="page">GIS Layers</a>
        </details>`;
    init();
    const group = document.getElementById('gis-tooling');
    expect(group.open).toBe(true);
    group.querySelector('summary').click();
    expect(group.open).toBe(false);
    group.querySelector('summary').click();
    expect(group.open).toBe(true);
});

it('does not require sidebar markup on other shells', () => {
    expect(() => init()).not.toThrow();
});
