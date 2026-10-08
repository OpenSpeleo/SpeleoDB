import { closeOpen, createOpenScope, isOpen, openMenu, toggleOpen } from './menu.ts';
import type { AlpineBindings, OpenScope } from '../../ts-types/browser/alpine.d.ts';

/** Typed bindings retain revision-specific prevent, focus, Escape and clone policies. */
export const revisionBindings = {
    'revision-project-revision_history-1': {
        'x-data': createOpenScope,
    },
    'revision-project-revision_history-2': {
        ':class'(this: OpenScope) { return this.open ? 'bg-slate-700 text-slate-400': 'text-slate-500 hover:text-slate-400'; },
        '@click.prevent': toggleOpen,
        ':aria-expanded': isOpen,
    },
    'revision-project-revision_history-3': {
        '@click.outside': closeOpen,
        '@keydown.escape.window': closeOpen,
        'x-show': isOpen,
    },
    'revision-project-revision_history-4': {
        '@click': closeOpen,
        '@focus': openMenu,
        '@focusout': closeOpen,
    },
    'revision-project-revision_history-5': {
        'x-data': createOpenScope,
    },
    'revision-controllers-revision-history-1': {
        'x-data': createOpenScope,
    },
    'revision-controllers-revision-history-2': {
        '@click': toggleOpen,
    },
    'revision-controllers-revision-history-3': {
        '@click.outside': closeOpen,
        'x-show': isOpen,
    },
} satisfies AlpineBindings;
