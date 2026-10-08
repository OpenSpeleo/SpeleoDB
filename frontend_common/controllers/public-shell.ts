import { registerAlpineBindings } from '../runtime/alpine.ts';
import { publicBindings } from '../bindings/public.ts';
import { initPublicShell } from '../../frontend_public/static/ts/main.ts';

export async function init(): Promise<void> {
    registerAlpineBindings(publicBindings);
    initPublicShell();
}
