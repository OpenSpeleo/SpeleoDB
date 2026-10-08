import type { JSONValue } from '../domain/json.ts';

export interface GeoJSONValueNode {
    parent: number;
    key: string | number;
    value: JSONValue;
    id?: never;
    array?: never;
}

export interface GeoJSONContainerNode {
    parent: number;
    key: string | number;
    id: number;
    array: boolean;
    value?: never;
}

export type GeoJSONNode = GeoJSONValueNode | GeoJSONContainerNode;

export type GeoJSONMessage =
    | { type: 'result'; data: JSONValue }
    | { type: 'start'; array: boolean }
    | { type: 'nodes'; nodes: GeoJSONNode[] }
    | { type: 'complete' };

export type GeoJSONWorkerRequest =
    | { type: 'parse'; buffer: ArrayBuffer; batchSize: number }
    | { type: 'next' };

export type GeoJSONWorkerResponse = GeoJSONMessage | { type: 'error' };
