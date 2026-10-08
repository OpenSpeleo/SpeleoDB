import { getMapOverlayHost, isVisibleMapElement, getActiveMapDialog, isMapDialogOpen } from './overlay_host.ts';

afterEach(() => { document.body.innerHTML = ''; });

it('uses the fullscreen shell when present and otherwise returns the existing body', () => {
    expect(getMapOverlayHost()).toBe(document.body);
    const shell = document.createElement('div');
    shell.id = 'map-viewer-shell';
    document.body.append(shell);
    expect(getMapOverlayHost()).toBe(shell);
});

it('rejects detached, missing, hidden and ancestor-hidden elements', () => {
    expect(isVisibleMapElement(null)).toBe(false);
    expect(isVisibleMapElement(undefined)).toBe(false);
    expect(isVisibleMapElement(document.createElement('div'))).toBe(false);
    document.body.innerHTML = '<section><div id="target"></div></section>';
    const target = document.getElementById('target')!;
    const parent = target.parentElement!;
    expect(isVisibleMapElement(target)).toBe(true);
    parent.hidden = true;
    expect(isVisibleMapElement(target)).toBe(false);
    parent.hidden = false;
    parent.classList.add('hidden');
    expect(isVisibleMapElement(target)).toBe(false);
    parent.classList.remove('hidden');
    parent.style.display = 'none';
    expect(isVisibleMapElement(target)).toBe(false);
    parent.style.display = '';
    parent.style.visibility = 'hidden';
    expect(isVisibleMapElement(target)).toBe(false);
});

it('prefers the last open native dialog over later legacy overlays', () => {
    document.body.innerHTML = '<dialog open id="first"></dialog><dialog open id="last"></dialog><div role="dialog" id="legacy"></div>';
    expect(getActiveMapDialog()).toBe(document.getElementById('last')!);
    expect(isMapDialogOpen()).toBe(true);
    document.getElementById('last')!.removeAttribute('open');
    expect(getActiveMapDialog()).toBe(document.getElementById('first')!);
});

it('recognizes only visible supported legacy overlays and returns null when none remain', () => {
    document.body.innerHTML = '<dialog></dialog><div class="fixed inset-0" id="decoration"></div><div class="fixed inset-0" id="photo-lightbox"></div><div id="map-managers-menu" hidden></div>';
    expect(getActiveMapDialog()).toBe(document.getElementById('photo-lightbox')!);
    document.getElementById('map-managers-menu')!.hidden = false;
    expect(getActiveMapDialog()).toBe(document.getElementById('map-managers-menu')!);
    document.getElementById('map-managers-menu')!.hidden = true;
    document.getElementById('photo-lightbox')!.classList.add('hidden');
    expect(getActiveMapDialog()).toBeNull();
    expect(isMapDialogOpen()).toBe(false);
});
