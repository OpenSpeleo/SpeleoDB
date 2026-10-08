import type { EntityId } from '../../../../../../ts-types/domain/identifiers.ts';
import { State } from '../state.ts';

/** Read the individual preference independently of the country gate. */
export function isProjectVisible(projectId: EntityId): boolean {
    try {
        return State.projectLayerStates.get(String(projectId)) !== false;
    } catch (e) {
        return true;
    }
}

/**
 * Whether a project is effectively visible on the map.
 * Checks effectiveProjectVisibility (set by applyProjectLayerVisibility)
 * first; falls back to individual preference for projects that haven't
 * been applied yet.
 */
export function isProjectEffectivelyVisible(
    projectId: EntityId,
    individualPreference: (projectId: string) => boolean = isProjectVisible,
): boolean {
    const pid = String(projectId);
    if (State.effectiveProjectVisibility.has(pid)) {
        return State.effectiveProjectVisibility.get(pid)!;
    }
    return individualPreference(pid);
}
