import { PagePlaceholder } from '~/components/layout/page-placeholder';

export function meta() {
  return [
    { title: 'FAQ | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Frequently asked questions',
    },
  ];
}

export default function Faq() {
  return (
    <PagePlaceholder
      title="Frequently Asked Questions"
      description="Answers to common questions about finding models, contributing your own, and running simulations are on the way."
    />
  );
}
