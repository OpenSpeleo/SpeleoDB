import type { ApiRequestOptions as SdkRequestOptions } from '@speleodb/api';
import type { ApiRequestError } from '../../frontend_common/api/client.ts';
export type ApiRequestOptions = Pick<SdkRequestOptions, 'signal'>;
/** UI error fields retained by the browser adapter. */
export type ApiError = Error & Pick<ApiRequestError, 'data' | 'status'>;
