import type { Map } from 'maplibre-gl';

/** Real renderer APIs used to observe visible output or target browser interactions. */
export type EvidenceMap = Pick<Map, 'on' | 'loaded' | 'isMoving' | 'project' | 'getLayer' | 'queryRenderedFeatures'>;

export interface ViewerEvidence {
    map: EvidenceMap;
    rendererIdle: boolean;
}
declare global { interface Window { __viewerEvidence: ViewerEvidence } }
