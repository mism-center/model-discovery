import SearchSection from '~/components/sections/search/search';

export function meta() {
  return [
    { title: 'Search | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Search for multiscale models and datasets',
    },
  ];
}

export default function Search() {
  return <SearchSection />;
}
