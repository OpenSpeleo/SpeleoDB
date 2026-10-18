import type { UserPermissionOptions } from '../domain/forms/permissions.ts';
import type { PermissionResource } from '../../frontend_common/api/permissions.ts';
export interface PermissionModalContext extends Omit<UserPermissionOptions, 'operations'> { resource: PermissionResource; entityId: string }
