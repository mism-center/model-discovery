import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';

type ApiClientType = Client<paths>;

export type BioModelsImportResponse =
  components['schemas']['BioModelsImportResponse'];

/**
 * Import a BioModels model into the registry as a draft awaiting annotation.
 *
 * Downloads the OMEX archive and fires the annotation run server-side, so this
 * is slower than a typical mutation. Requires an authenticated caller.
 */
export async function importBioModelsModel(
  modelId: string,
  options: { signal?: AbortSignal; client?: ApiClientType } = {}
): Promise<BioModelsImportResponse> {
  const { data } = await (options.client ?? apiClient).POST(
    '/api/v1/imports/biomodels',
    {
      body: { model_id: modelId },
      signal: options.signal,
    }
  );
  // errorMiddleware throws on non-2xx, so data is always defined here.
  return data as BioModelsImportResponse;
}
