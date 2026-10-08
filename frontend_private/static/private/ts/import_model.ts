import type { ImportReview, ImportEligibility } from '../../../../ts-types/domain/data-import.ts';

export const count = (value: unknown) => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;
export const plural = (value: unknown, singular: string, multiple = `${singular}s`) => `${count(value)} ${count(value) === 1 ? singular : multiple}`;

export function canImportKML({ file, report, mode, collectionId, layerName, busy = false, uncertain = false }: ImportEligibility) {
    if (!file || !report || busy || uncertain) return false;
    if (mode === 'places') return count(report.places?.unique_coordinate_count) > 0 && Boolean(collectionId);
    if (mode === 'overlay') return count(report.overlay?.feature_count) > 0 && Boolean(layerName?.trim());
    return false;
}

export function validReport(value: unknown): value is ImportReview {
    const report = value as ImportReview | null;
    return (report?.places && report?.overlay && Array.isArray(report.warnings)
        && Number.isFinite(report.places.unique_coordinate_count)
        && Number.isFinite(report.overlay.feature_count)) as boolean;
}
