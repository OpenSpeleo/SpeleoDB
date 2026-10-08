import type { ColorMode, DepthDomain, DisplayPreferences } from './map-display.ts';

export interface DepthDomainEventDetail {
    domain: DepthDomain | null;
    available: boolean;
    max: number | null;
}

/** Display notifications are Window events; detail-free events stay detail-free. */
export type DisplayEvent =
    | { type: 'speleo:display-update-pending' | 'speleo:display-update-applied'; detail?: never }
    | { type: 'speleo:display-update-failed'; detail: { error: unknown } }
    | { type: 'speleo:color-mode-changed'; detail: { mode: ColorMode } }
    | { type: 'speleo:display-preferences-changed'; detail: { preferences: DisplayPreferences } }
    | { type: 'speleo:depth-domain-updated' | 'speleo:depth-data-updated'; detail: DepthDomainEventDetail };
