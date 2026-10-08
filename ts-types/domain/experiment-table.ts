export interface ExperimentTableField {
    id: string;
    name: string;
    order?: number;
}
/** Backend custom field UUIDs and display names are open keys. */
export type ExperimentTableRow = Record<string, unknown>;
export interface ExperimentTableFeature {
    properties?: Record<string, unknown>;
    geometry?: { coordinates?: number[] };
}
export interface ExperimentTableDefinition {
    data?: { experiment_fields?: ExperimentTableField[] | Record<string, unknown> };
    experiment_fields?: ExperimentTableField[] | Record<string, unknown>;
}
export interface ExperimentTableGeoJSON { features?: ExperimentTableFeature[] }
