export function init() {
    const group = document.getElementById('gis-tooling');
    if (group?.querySelector('a[aria-current="page"]')) group.open = true;
}
