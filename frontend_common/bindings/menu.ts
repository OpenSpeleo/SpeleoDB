import type { AlpineBinding, AlpineBindings, AlpineElementScope, OpenScope } from '../../ts-types/browser/alpine.d.ts';

export function createOpenScope(this: AlpineElementScope) { return { open: false }; }
export function toggleOpen(this: OpenScope) { return this.open = !this.open; }
export function closeOpen(this: OpenScope) { return this.open = false; }
export function openMenu(this: OpenScope) { return this.open = true; }
export function isOpen(this: OpenScope) { return this.open; }

/** Entity menus share click/outside behavior; they intentionally add no ARIA, Escape or focus handlers. */
export function entityMenuBindings(prefix: string, closeLinkCount: number): AlpineBindings {
    const bindings: Record<string, AlpineBinding> = {
        [`${prefix}-1`]: { 'x-data': createOpenScope },
        [`${prefix}-2`]: {
            '@click': toggleOpen,
            ':class'(this: OpenScope) { return this.open ? 'open' : ''; },
        },
        [`${prefix}-3`]: { 'x-show': isOpen, '@click.outside': closeOpen },
    };
    for (let index = 0; index < closeLinkCount; index++) {
        bindings[`${prefix}-${index + 4}`] = { '@click': closeOpen };
    }
    return bindings;
}
