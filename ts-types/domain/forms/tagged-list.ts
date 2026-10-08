export interface TaggedEntity { id: string | number }
export interface TaggedListApi {
    reload: () => void;
    openEditModal: (entityId: string | number) => void;
    openDeleteModal: (entityId: string | number) => void;
}
export interface TaggedListOptions<Entity extends TaggedEntity> {
    listEndpoint?: string | undefined;
    detailEndpointBuilder?: (id: string | number) => string;
    editMethod?: string;
    createMethod?: string;
    renderList?: (entities: Entity[], api: TaggedListApi) => void;
    openEditModalForEntity?: (entity: Entity) => void;
    resetEditModal?: () => void;
    collectEditPayload?: () => unknown;
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
