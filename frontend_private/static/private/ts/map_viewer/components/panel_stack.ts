import { DEFAULTS } from '../defaults.ts';

function slotFor(panelId: string) {
    return document.getElementById(panelId)?.closest<HTMLElement>('.map-panel-slot');
}

/** Panel disclosure affects only the menus, never their map visibility controls. */
export function setMapPanelExpanded(panelId: string, expanded: boolean) {
    const slot = slotFor(panelId);
    if (!slot) return;
    const panel = document.getElementById(panelId)!;
    const minimized = document.getElementById(`${panelId}-minimized`)!;
    const expand = minimized.matches('button') ? minimized : minimized.querySelector('button')!;
    const collapse = panel.querySelector<HTMLButtonElement>('.map-panel-collapse')!;
    const restoreFocus = slot.contains(document.activeElement);

    if (expanded) {
        for (const sibling of slot.parentElement!.querySelectorAll<HTMLElement>('.map-panel-slot.is-expanded')) {
            const siblingPanel = sibling.querySelector<HTMLElement>('.map-panel-card');
            if (siblingPanel && siblingPanel !== panel) setMapPanelExpanded(siblingPanel.id, false);
        }
    }
    slot.classList.toggle('is-expanded', expanded);
    panel.hidden = !expanded;
    panel.style.display = expanded ? 'flex' : 'none';
    minimized.hidden = expanded;
    minimized.style.display = expanded ? 'none' : 'flex';
    expand.setAttribute('aria-expanded', String(expanded));
    collapse.setAttribute('aria-expanded', String(expanded));
    if (restoreFocus) (expanded ? collapse : expand).focus({ preventScroll: true });
}

/** Register existing controls in one naturally flowing, alphabetic accordion. */
export function registerMapPanel(panelId: string, expandId: string, collapseId: string, expanded = false) {
    const panel = document.getElementById(panelId);
    const minimized = document.getElementById(`${panelId}-minimized`);
    const expand = document.getElementById(expandId);
    const collapse = document.getElementById(collapseId);
    const map = document.getElementById('map');
    if (!panel || !minimized || !expand || !collapse || !map) return;

    let stack = document.getElementById('map-panel-stack');
    if (!stack) {
        stack = document.createElement('div');
        stack.id = 'map-panel-stack';
        stack.className = 'map-panel-stack';
        stack.style.setProperty('--map-panel-edge', `${DEFAULTS.UI.MAP_PANEL_EDGE_PX}px`);
        stack.style.setProperty('--map-panel-gap', `${DEFAULTS.UI.MAP_PANEL_GAP_PX}px`);
        for (const event of ['click', 'mousedown', 'dblclick', 'touchstart', 'wheel', 'contextmenu']) {
            stack.addEventListener(event, e => e.stopPropagation());
        }
        map.append(stack);
    }
    let slot = slotFor(panelId);
    const alreadyRegistered = Boolean(slot);
    if (!slot) {
        slot = document.createElement('div');
        slot.className = 'map-panel-slot';
        if (panelId !== 'gis-geometries-panel') slot.classList.add('map-panel-slot--desktop');
        slot.append(panel, minimized);
        stack.append(slot);
    }
    panel.classList.add('map-panel-card');
    minimized.classList.add('map-panel-minimized');
    collapse.classList.add('map-panel-collapse');
    for (const control of [expand, collapse]) {
        control.setAttribute('aria-controls', panelId);
        control.setAttribute('type', 'button');
    }
    expand.onclick = () => setMapPanelExpanded(panelId, true);
    collapse.onclick = () => setMapPanelExpanded(panelId, false);
    if (!alreadyRegistered) {
        const title = panel.querySelector('h3')?.textContent || '';
        const following = [...stack.children].find(child => child !== slot
            && title.localeCompare(child.querySelector('h3')?.textContent || '', undefined, { sensitivity: 'base' }) < 0);
        stack.insertBefore(slot, following || null);
    }
    setMapPanelExpanded(panelId, alreadyRegistered ? slot.classList.contains('is-expanded') : expanded);
}

export function unregisterMapPanel(panelId: string) {
    const slot = slotFor(panelId);
    const stack = slot?.parentElement;
    slot?.remove();
    if (stack && !stack.children.length) stack.remove();
}
