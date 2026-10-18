export interface TaggedEntity { id: string | number }
export interface TaggedListApi {
    reload: () => void;
    openEditModal: (entityId: string | number) => void;
    openDeleteModal: (entityId: string | number) => void;
}
export interface TaggedListOptions<Entity extends TaggedEntity, Payload = unknown> {
    list: () => Promise<Entity[]>;
    create?: (payload: Payload) => Promise<unknown>;
    update?: (id: string | number, payload: Payload) => Promise<unknown>;
    remove?: (id: string | number) => Promise<unknown>;
    renderList?: (entities: Entity[], api: TaggedListApi) => void;
    openEditModalForEntity?: (entity: Entity) => void;
    resetEditModal?: () => void;
    collectEditPayload?: () => Payload | null;
    openDeleteModalForEntity?: (entity: Entity) => void;
    editFormSelector?: string;
    editIdInputSelector?: string;
    editModalSelector?: string;
    editModalTitleSelector?: string;
    createModalTitle?: string;
    editModalTitle?: string;
    createBtnSelector?: string;
    closeEditModalSelectors?: string;
    createSubmitLabelSelector?: string;
    createSubmitLabel?: string;
    editSubmitLabel?: string;
    deleteModalSelector?: string;
    deleteIdInputSelector?: string;
    confirmDeleteSelector?: string;
    closeDeleteModalSelectors?: string;
    entityLabel?: string;
    entityLabelPlural?: string;
    loadFailedMessage?: string;
}
