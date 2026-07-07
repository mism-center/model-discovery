import { redirect } from 'react-router';
import type { Route } from './+types/index';

export function loader({ request }: Route.LoaderArgs) {
  const { search } = new URL(request.url);
  return redirect(`/search${search}`);
}

export default function Index() {
  return null;
}
