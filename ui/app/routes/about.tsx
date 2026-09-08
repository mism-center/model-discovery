import { PagePlaceholder } from '~/components/layout/page-placeholder';

export function meta() {
  return [
    { title: 'About | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - About the portal',
    },
  ];
}

export default function About() {
  return (
    <PagePlaceholder
      title="About the Multiscale Model Portal"
      description="We're putting together an overview of the portal, the Multiscale Immune Systems Modeling center behind it, and how the model catalog is curated."
    />
  );
}
