import { registerAlpineBindings } from '../runtime/alpine.ts';
import { privateBindings } from '../bindings/private.ts';
export function init() {
    registerAlpineBindings(privateBindings);
    const group = document.getElementById('gis-tooling') as HTMLDetailsElement | null;
    if (group?.querySelector('a[aria-current="page"]')) group.open = true;
}
