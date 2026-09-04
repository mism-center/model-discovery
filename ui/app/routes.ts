import { type RouteConfig, index, route } from '@react-router/dev/routes';

export default [
  index('routes/index.tsx'),
  route('search', 'routes/search.tsx'),
  route('models/:id', 'routes/model-details.tsx'),
  route('runs', 'routes/runs.tsx'),
  route('upload', 'routes/upload.tsx'),
  route('annotation-review', 'routes/annotation-review.tsx'),
  // Linked from the Header/Footer; placeholder content until designed.
  route('about', 'routes/about.tsx'),
  route('faq', 'routes/faq.tsx'),
  route('support', 'routes/support.tsx'),
  route('privacy', 'routes/privacy.tsx'),
  route('healthz', 'routes/healthz.tsx'),
] satisfies RouteConfig;
