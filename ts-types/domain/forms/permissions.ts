export interface PermissionSelectors {
    openAddBtn: string;
    openEditBtn: string;
    deleteBtn: string;
    modal: string;
    modalTitle: string;
    modalHeader: string;
    form: string;
    submitBtn: string;
    closeBtn: string;
}
export interface TeamPermissionOptions {
    endpoint?: string;
    addModalTitle?: string;
    addModalHeader?: string;
    editModalTitle?: string;
    fieldLabel?: string;
    reloadDelayMs?: number;
}
export interface UserPermissionOptions extends TeamPermissionOptions {
    autocompleteUrl?: string;
    fieldName?: 'level' | 'role';
    successMessage?: string;
    deleteMessage?: string;
    selectors?: Partial<PermissionSelectors>;
}
