import { PagePlaceholder } from '~/components/layout/page-placeholder';

export function meta() {
  return [
    { title: 'User Support | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - User support',
    },
  ];
}

export default function Support() {
  return (
    <PagePlaceholder
      title="User Support"
      description="Guides, troubleshooting, and a way to reach the team are coming soon. In the meantime, email us and we'll help you out."
    />
  );
}
