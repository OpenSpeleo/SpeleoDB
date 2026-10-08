export interface CopyButtonOptions {
    button: string;
    text: string;
    value: string;
    icon?: string;
    disabledGuard?: boolean;
}
export interface TokenModalOptions {
    form: string;
    modal: string;
    cancel: string;
    confirm: string;
    namedSubmit?: boolean;
}
export interface CopyTokenContext {
    waitForWindowLoad?: boolean;
    copyButtons?: CopyButtonOptions[];
    tokenModal?: TokenModalOptions;
}
