import { closeOpen, createOpenScope, entityMenuBindings, isOpen, toggleOpen } from './menu.ts';
import type { AlpineBindings, AlpineElementScope, SidebarScope, PreferenceScope } from '../../ts-types/browser/alpine.d.ts';

/** Typed bindings preserve each original element policy and independent scope state. */
export const privateBindings = {
    'private-templates-base_private-1': {
        'x-data'(this: AlpineElementScope) { return { sidebarOpen: false }; },
    },
    'private-templates-base_private-2': {
        ':class'(this: SidebarScope) { return this.sidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'; },
    },
    'private-templates-base_private-3': {
        ':class'(this: SidebarScope) { return this.sidebarOpen ? 'translate-x-0' : '-translate-x-full'; },
        '@click.outside'(this: SidebarScope) { return this.sidebarOpen = false; },
        '@keydown.escape.window'(this: SidebarScope) { return this.sidebarOpen = false; },
    },
    'private-templates-base_private-4': {
        '@click.stop'(this: SidebarScope) { return this.sidebarOpen = !this.sidebarOpen; },
        ':aria-expanded'(this: SidebarScope) { return this.sidebarOpen; },
    },
    'private-templates-base_private-5': {
        '@click.stop'(this: SidebarScope) { return this.sidebarOpen = !this.sidebarOpen; },
        ':aria-expanded'(this: SidebarScope) { return this.sidebarOpen; },
    },
    'private-templates-base_private-6': {
        'x-data': createOpenScope,
    },
    'private-templates-base_private-7': {
        '@click.prevent': toggleOpen,
        ':aria-expanded': isOpen,
    },
    'private-templates-base_private-8': {
        '@click.outside': closeOpen,
        '@keydown.escape.window': closeOpen,
        'x-show': isOpen,
    },
    ...entityMenuBindings('private-cylinder_fleet-base', 7),
    ...entityMenuBindings('private-experiment-base', 5),
    ...entityMenuBindings('private-gis_view-base', 3),
    ...entityMenuBindings('private-project-base', 8),
    ...entityMenuBindings('private-sensor_fleet-base', 5),
    ...entityMenuBindings('private-surface_network-base', 4),
    ...entityMenuBindings('private-team-base', 3),
    ...entityMenuBindings('private-tools-base', 4),
    ...entityMenuBindings('private-user-base', 5),
    ...entityMenuBindings('private-entity_settings-base', 3),
    'private-user-preferences-1': {
        'x-data'(this: PreferenceScope) { return { checked: this.$el.dataset.speleodbChecked === 'true' }; },
    },
    'private-user-preferences-2': {
        'x-text'(this: PreferenceScope) { return this.checked ? 'On' : 'Off'; },
    },
    'private-user-preferences-3': {
        'x-model'(this: PreferenceScope) { return { get: () => this.checked, set: (value: boolean) => { this.checked = value; } }; },
    },
    'private-user-preferences-4': {
        'x-data'(this: PreferenceScope) { return { checked: this.$el.dataset.speleodbChecked === 'true' }; },
    },
    'private-user-preferences-5': {
        'x-text'(this: PreferenceScope) { return this.checked ? 'On' : 'Off'; },
    },
    'private-user-preferences-6': {
        'x-model'(this: PreferenceScope) { return { get: () => this.checked, set: (value: boolean) => { this.checked = value; } }; },
    },
} satisfies AlpineBindings;
