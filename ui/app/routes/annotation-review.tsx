import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
  HydrationBoundary,
  dehydrate,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { Button, Card, CardBody, Spinner } from '@heroui/react';

import { requireUser } from '~/api/auth/require-user';
import { resourceDownloadUrl } from '~/api/endpoints/resources';
import {
  modelAnnotationPackageQueryOptions,
  modelDetailQueryOptions,
  modelKeys,
} from '~/api/query/models';
import { resourceFilesQueryOptions } from '~/api/query/resources';
import { MetadataFormViewer } from '~/components/sections/upload/metadata-form-viewer';
import type { Route } from './+types/annotation-review';

export function meta() {
  return [
    { title: 'Annotation Review | MISM' },
    {
      name: 'description',
      content: 'Review and approve annotation metadata for a model.',
    },
  ];
}

/**
 * Auth-gated route, mirroring `runs.tsx`.
 *
 * Reviewing an annotation is a privileged action and every endpoint behind this
 * page 401s for anonymous callers, so the gate belongs at the boundary:
 * `requireUser` resolves the session server-side and redirects into the login
 * flow before the route renders. Previously nothing gated it — the only entry
 * point (the pending-review card) is hidden without a user, but navigating
 * straight to `/annotation-review?id=…` rendered the page shell and left every
 * query to fail into an error state. Hidden is not locked.
 *
 * `returnToKey` carries the `?id=` query through login via `return_to_query`, so
 * the reviewer lands back on the model they were opening.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const { client, queryClient } = await requireUser(request, {
    returnToKey: 'annotation-review',
  });

  const url = new URL(request.url);
  const modelId = url.searchParams.get('id') ?? '';

  if (modelId) {
    await Promise.all([
      queryClient.prefetchQuery(modelDetailQueryOptions(modelId, client)),
      queryClient.prefetchQuery(
        modelAnnotationPackageQueryOptions(modelId, client)
      ),
    ]);
  }

  return { dehydratedState: dehydrate(queryClient), modelId };
}

export default function AnnotationReviewPage({
  loaderData,
}: Route.ComponentProps) {
  return (
    <HydrationBoundary state={loaderData.dehydratedState}>
      <AnnotationReviewContent modelId={loaderData.modelId} />
    </HydrationBoundary>
  );
}

function AnnotationReviewContent({ modelId }: { modelId: string }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [savedStatus, setSavedStatus] = useState<string | null>(null);
  const [saveError, setSaveError] = useState('');

  const { data: model, isPending: modelPending } = useQuery({
    ...modelDetailQueryOptions(modelId),
    enabled: !!modelId,
  });
  const { data: annotationPackage, isPending: pkgPending } = useQuery({
    ...modelAnnotationPackageQueryOptions(modelId),
    enabled: !!modelId,
  });
  const { data: resourceFiles } = useQuery({
    ...resourceFilesQueryOptions(modelId),
    enabled: !!modelId,
  });

  if (!modelId) {
    return (
      <div className="p-6">
        <p className="text-sm text-default-600">
          No model ID in URL — add{' '}
          <code className="font-mono">?id=MODEL_ID</code>
        </p>
      </div>
    );
  }

  if (modelPending || pkgPending) {
    return (
      <div className="flex justify-center p-12">
        <Spinner />
      </div>
    );
  }

  const annotationStatus = savedStatus ?? model?.registration_status ?? '';
  const rawFiles = annotationPackage?.files ?? [];
  const outputFiles = (resourceFiles?.files ?? []).filter(
    (f) =>
      !f.is_dir &&
      f.path.startsWith('metadata-package/') &&
      !f.name.startsWith('.')
  );

  return (
    <main className="container mx-auto p-6 flex flex-col gap-6 max-w-4xl">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Annotation Review</h1>
        <p className="text-sm text-foreground">
          Inspect and approve the metadata annotation generated for this model.
        </p>
        {model?.name && (
          <div className="mt-4 pt-4 border-t border-default-200">
            <h2 className="text-xl font-bold font-headline text-primary">
              {model.name}
            </h2>
            {model.description && (
              <p className="text-sm text-default-700 mt-1 leading-relaxed">
                {model.description}
              </p>
            )}
          </div>
        )}
      </header>
      <Card shadow="sm" className="border-success-200 bg-success-50">
        <CardBody className="flex flex-col gap-1">
          <span className="text-lg font-medium text-foreground">
            Annotation complete
          </span>
          {annotationStatus && (
            <span className="text-xs text-default-800">
              Status:{' '}
              <code className="font-mono font-bold text-default-900">
                {annotationStatus}
              </code>
            </span>
          )}
          <span className="text-xs text-default-800">
            Model ID: <code className="font-mono">{modelId}</code>
          </span>
          {rawFiles.length > 0 && (
            <div className="mt-2">
              <MetadataFormViewer
                modelId={modelId}
                rawFiles={rawFiles}
                onSaved={() => {
                  setSavedStatus('approved');
                  setSaveError('');
                  queryClient.invalidateQueries({
                    queryKey: modelKeys.pendingReview(),
                  });
                }}
                onSaveError={(msg) => {
                  setSaveError(msg);
                }}
                annotationFiles={outputFiles.map((f) => ({
                  path: f.path,
                  name: f.name,
                  url: resourceDownloadUrl(modelId, f.path),
                }))}
              />
              {saveError && (
                <span className="text-xs text-danger-600 mt-1">
                  {saveError}
                </span>
              )}
            </div>
          )}
          <div className="mt-3">
            <Button
              size="sm"
              color="success"
              variant="flat"
              className="text-foreground"
              onPress={() => navigate('/search')}
            >
              Return to the Search page
            </Button>
          </div>
        </CardBody>
      </Card>
    </main>
  );
}
