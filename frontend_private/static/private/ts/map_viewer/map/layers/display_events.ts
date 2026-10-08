import type { DisplayEvent } from '../../../../../../../ts-types/domain/map-display-events.ts';

/** Publish display state without copying mutable payloads or adding absent detail. */
export function publishDisplayEvent(event: DisplayEvent): void {
    window.dispatchEvent('detail' in event
        ? new CustomEvent(event.type, { detail: event.detail })
        : new CustomEvent(event.type));
}
