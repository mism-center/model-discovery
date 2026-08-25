import { type RouteConfig, index, route } from '@react-router/dev/routes';

export default [
  index('routes/index.tsx'),
  route('search', 'routes/search.tsx'),
  route('models/:id', 'routes/model-details.tsx'),
  route('runs', 'routes/runs.tsx'),
  route('pending-reviews', 'routes/pending-reviews.tsx'),
  route('upload', 'routes/upload.tsx'),
  route('annotation-review', 'routes/annotation-review.tsx'),
  route('healthz', 'routes/healthz.tsx'),
] satisfies RouteConfig;
