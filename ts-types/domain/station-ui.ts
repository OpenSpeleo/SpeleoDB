import type { EntityId } from './identifiers.ts';
export type StationFamily = 'subsurface' | 'surface';
export interface StationManagerNavigation { subsurface?: () => unknown; surface?: () => unknown }
export interface StationManagerOptions { returnFocus?: HTMLElement | null }
export type StationParentId = EntityId | null | undefined;
