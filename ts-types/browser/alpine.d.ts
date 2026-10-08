export interface AlpineElementScope { $el: HTMLElement }
export interface OpenScope extends AlpineElementScope { open: boolean }
export interface SidebarScope extends AlpineElementScope { sidebarOpen: boolean }
export interface MobileScope extends AlpineElementScope { expanded: boolean; $refs: { mobileNav: HTMLElement } }
export interface WelcomeScope extends AlpineElementScope { showModal: boolean }
export interface PreferenceScope extends AlpineElementScope { checked: boolean }
type AlpineDirective = 'x-data' | 'x-show' | 'x-text' | 'x-model' | ':class' | ':style' | ':aria-expanded'
    | '@click' | '@click.stop' | '@click.prevent' | '@click.outside' | '@keydown.escape.window' | '@focus' | '@focusout';
export type AlpineBinding = Partial<Record<AlpineDirective, (this: never) => unknown>>;
/** Inert binding names are a registry boundary, not arbitrary scope properties. */
export type AlpineBindings = Readonly<Record<string, AlpineBinding>>;
export interface AlpineRuntime {
    addRootSelector(callback: () => string): void;
    bind(element: Element, bindings: AlpineBinding): void;
    interceptInit(callback: (element: Element) => void): void;
    initTree(element: Element): void;
    nextTick(): Promise<void>;
}
declare global { interface Window { Alpine?: AlpineRuntime } }
