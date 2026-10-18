import type { GeoJSONMessage } from '@speleodb/map-core/geojson-transport';

export type GeoJSONWorkerRequest =
    | { type: 'parse'; buffer: ArrayBuffer; batchSize: number }
    | { type: 'next' };

export type GeoJSONWorkerResponse = GeoJSONMessage | { type: 'error' };
