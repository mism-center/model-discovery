import { redirect } from 'react-router';

export function loader() {
  return redirect('/search');
}

export default function Index() {
  return null;
}
