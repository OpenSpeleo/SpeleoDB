export interface OpenMapDialogOptions {
    closeButton?: HTMLElement | string | null;
    returnFocus?: HTMLElement | null;
    onClose?: (() => void) | null;
    dismissOnBackdrop?: boolean;
    canDismiss?: () => boolean;
}
export interface MapDialogRecord {
    trigger: HTMLElement | null;
    onClose: (() => void) | null;
    keydown: (event: KeyboardEvent) => void;
    canDismiss: () => boolean;
}
export interface ContextMenuItem {
    icon?: string;
    label: string;
    subtitle?: string | undefined;
    disabled?: boolean;
    onClick?: () => unknown;
}
export type ContextMenuEntry = '-' | ContextMenuItem;
