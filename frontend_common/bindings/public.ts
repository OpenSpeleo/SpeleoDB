import type { AlpineBindings, AlpineElementScope, MobileScope, WelcomeScope } from '../../ts-types/browser/alpine.d.ts';

/** Literal bindings retain each original template element and scope factory. */
export const publicBindings = {
    'public-templates-base-1': {
        'x-data'(this: AlpineElementScope) { return { expanded: false }; },
    },
    'public-templates-base-2': {
        ':class'(this: MobileScope) { return { 'active': this.expanded }; },
        '@click.stop'(this: MobileScope) { return this.expanded = !this.expanded; },
        ':aria-expanded'(this: MobileScope) { return this.expanded; },
    },
    'public-templates-base-3': {
        ':style'(this: MobileScope) { return this.expanded ? 'max-height: ' + this.$refs.mobileNav.scrollHeight + 'px; opacity: 1' : 'max-height: 0; opacity: .8'; },
        '@click.outside'(this: MobileScope) { return this.expanded = false; },
        '@keydown.escape.window'(this: MobileScope) { return this.expanded = false; },
    },
    'public-pages-home-1': {
        'x-data'(this: AlpineElementScope) { return { tab: '1' }; },
    },
    'public-snippets-welcome_modal-1': {
        'x-data'(this: AlpineElementScope) { return { showModal: true }; },
        'x-show'(this: WelcomeScope) { return this.showModal; },
        '@keydown.escape.window'(this: WelcomeScope) { return this.showModal = false; },
    },
    'public-snippets-welcome_modal-2': {
        '@click'(this: WelcomeScope) { return this.showModal = false; },
    },
    'public-snippets-welcome_modal-3': {
        '@click'(this: WelcomeScope) { return this.showModal = false; },
    },
} satisfies AlpineBindings;
