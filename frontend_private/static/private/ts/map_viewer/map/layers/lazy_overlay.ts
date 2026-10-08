import type { LazyOverlayOptions, OverlayRequest, OverlayVersion } from '../../../../../../../ts-types/domain/map-layers.ts';
import { State } from '../../state.ts';
import { ViewerUpdates } from '../../viewer_updates.ts';
import { Utils } from '../../utils.ts';
import { cancelMapNavigation } from '../navigation_intent.ts';

// Data requests are shared independently of the serial map-application queue.
const overlayRequests = new Map<string, OverlayRequest>();
const overlayIntents = new Map<string, object>();
const overlayCachedVersions = new Map<string, OverlayVersion>();
const overlayAppliedVersions = new Map<string, OverlayVersion>();

export async function toggleLazyOverlay<Prepared>({ kind, id, visible, cache, states, layers, details, prepare, install, show, loading, metadata }: LazyOverlayOptions<Prepared>) {
    const key = `${kind}:${id}`;
    const intent = beginOverlayIntent(key);
    states.set(id, visible);
    const map = State.map;
    const generation = State.layerGeneration;
    const tracksMetadata = Boolean(metadata?.());
    const revision = () => metadata?.()?.modified_date ?? null;
    const sameSession = () => State.layerGeneration === generation && State.map === map;
    const ownsIntent = () => sameSession() && isOverlayIntentCurrent(key, intent);
    const entityExists = () => !tracksMetadata || Boolean(metadata?.());
    const current = () => ownsIntent() && entityExists();
    if (!visible) {
        loading?.(false);
        cancelMapNavigation(key);
        const result = await ViewerUpdates.schedule(key, () => { if (current()) show(false); });
        return current() && result.status === 'applied';
    }
    try {
        while (current() && states.get(id)) {
            const version = revision();
            const versionCurrent = () => current() && revision() === version;
            try {
                let data = cache.get(id);
                const cached = overlayCachedVersions.get(key);
                if (data && cached?.generation !== generation) {
                    // Adopt cached sources restored before this intent tracker first saw them.
                    const ids = layers.get(id);
                    if (ids?.length && map?.getLayer(ids[0]!)) {
                        overlayAppliedVersions.set(key, { generation, revision: version, data });
                    }
                }
                if (data && cached?.generation === generation && cached.data === data && cached.revision !== version) {
                    cache.delete(id);
                    data = undefined;
                }
                if (!data) {
                    loading?.(true);
                    let request = overlayRequests.get(key);
                    if (!request || request.generation !== generation || request.revision !== version) {
                        request?.controller.abort();
                        const controller = new AbortController();
                        // The following assignment preserves the original synchronous request construction.
                        request = { generation, revision: version, controller } as OverlayRequest;
                        request.promise = details(controller.signal);
                        overlayRequests.set(key, request);
                        // An older finalizer must not clear its replacement.
                        void request.promise.finally(() => {
                            if (overlayRequests.get(key) === request) overlayRequests.delete(key);
                        }).catch(() => {});
                    }
                    data = await request.promise;
                    if (!sameSession() || !entityExists()) return false;
                    // A list refresh may have published a newer file during the download.
                    if (revision() !== version) continue;
                    cache.set(id, data);
                }
                overlayCachedVersions.set(key, { generation, revision: version, data });
                if (!versionCurrent() || !states.get(id)) return false;
                const needsInstall = () => {
                    const ids = layers.get(id);
                    const applied = overlayAppliedVersions.get(key);
                    return !ids?.length || !map?.getLayer(ids[0]!) || applied?.generation !== generation
                        || applied.revision !== version || applied.data !== data;
                };
                const prepared = needsInstall() && prepare ? await prepare(data, versionCurrent) : undefined;
                if (!current()) return false;
                if (!versionCurrent()) continue;
                const result = await ViewerUpdates.schedule(key, async context => {
                    if (!versionCurrent() || !context.isCurrent()) return;
                    if (needsInstall()) {
                        await install(data, () => versionCurrent() && context.isCurrent(), prepared);
                        if (!versionCurrent() || !context.isCurrent()) return;
                        overlayAppliedVersions.set(key, { generation, revision: version, data });
                    }
                    show(states.get(id) === true);
                });
                if (!current()) return false;
                if (!versionCurrent()) continue;
                if (result.status === 'failed') throw result.error;
                return result.status === 'applied' && states.get(id) === true;
            } catch (error) {
                // Retry only a changed metadata revision, never a genuine failed request.
                if (current() && revision() !== version) continue;
                throw error;
            }
        }
        return false;
    } catch (error) {
        if (!current()) return false;
        states.set(id, false);
        cache.delete(id);
        show(false);
        console.error(`Failed to display ${kind}:`, error);
        Utils.showNotification('error', 'Unable to display this item. Toggle it on to retry.');
        return false;
    } finally {
        // Metadata removal invalidates rendering, but this intent still owns its spinner.
        if (ownsIntent()) loading?.(false);
    }
}

export function beginOverlayIntent(key: string): object {
    const intent = {};
    overlayIntents.set(key, intent);
    return intent;
}

export function isOverlayIntentCurrent(key: string, intent: object): boolean {
    return overlayIntents.get(key) === intent;
}

export function cancelLazyOverlays(): void {
    for (const request of overlayRequests.values()) request.controller.abort();
    overlayRequests.clear();
    overlayIntents.clear();
    overlayCachedVersions.clear();
    overlayAppliedVersions.clear();
}
