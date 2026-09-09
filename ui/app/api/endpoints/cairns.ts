import type { Client } from 'openapi-fetch';

import type { components, paths } from '~/api/generated/schema';
import { apiClient } from '~/api/client/client';

type ApiClientType = Client<paths>;

export type CairnsRecommendRequest =
  components['schemas']['CairnsRecommendRequest'];
export type CairnsRecommendResponse =
  components['schemas']['CairnsRecommendResponse'];
export type CairnsEvidenceCard = components['schemas']['CairnsEvidenceCardDTO'];

/**
 * Ask CAIRNS for computational models and tools matching a question.
 *
 * Retrieval plus LLM synthesis runs per request with no streaming: observed
 * 7-10s typical, and the gateway allows up to 180s before it returns 504.
 */
export async function recommend(
  request: CairnsRecommendRequest,
  options: { signal?: AbortSignal; client?: ApiClientType } = {}
): Promise<CairnsRecommendResponse> {
  const { data } = await (options.client ?? apiClient).POST(
    '/api/v1/cairns/recommend',
    {
      body: request,
      signal: options.signal,
    }
  );
  // errorMiddleware throws on non-2xx, so data is always defined here.
  return data as CairnsRecommendResponse;
}
