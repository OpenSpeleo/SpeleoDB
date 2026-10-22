import type { Map } from 'maplibre-gl';

/** Real renderer APIs used to observe visible output or target browser interactions. */
export type EvidenceMap = Pick<Map, 'on' | 'loaded' | 'isMoving' | 'project' | 'jumpTo' | 'getCanvas' | 'getLayer' | 'queryRenderedFeatures'>;

export interface ViewerEvidence {
    map: EvidenceMap;
    rendererIdle: boolean;
    canvasFrame?: { dataUrl: string; sequence: number };
}
declare global { interface Window { __viewerEvidence: ViewerEvidence } }
