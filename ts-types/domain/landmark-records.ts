import type { Landmark, PatchedLandmarkRequest, LandmarkCollectionWithPerm } from '@speleodb/api';
import type { EntityId } from './identifiers.ts';

export type LandmarkWrite = PatchedLandmarkRequest;
/** Local map records can precede a persisted landmark and omit server timestamps. */
export interface LandmarkRecord extends Partial<Omit<Landmark, 'id'>> { id: EntityId }
export type LandmarkCollectionRecord = LandmarkCollectionWithPerm;
