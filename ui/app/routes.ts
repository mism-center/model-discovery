import { type RouteConfig, index, route } from '@react-router/dev/routes';

export default [
  index('routes/index.tsx'),
  route('search', 'routes/search.tsx'),
  route('tus-test', 'routes/tus-test.tsx'),
] satisfies RouteConfig;
