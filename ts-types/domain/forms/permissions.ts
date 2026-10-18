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
    operations: PermissionOperations;
    addModalTitle?: string;
    addModalHeader?: string;
    editModalTitle?: string;
    fieldLabel?: string;
    reloadDelayMs?: number;
}
export interface UserPermissionOptions extends TeamPermissionOptions {
    fieldName?: 'level' | 'role';
    successMessage?: string;
    deleteMessage?: string;
    selectors?: Partial<PermissionSelectors>;
}
import type { FormPayload } from './crud.ts';

export interface PermissionOperations {
    create: (payload: FormPayload) => Promise<unknown>;
    update: (payload: FormPayload) => Promise<unknown>;
    remove: (payload: FormPayload) => Promise<unknown>;
}
