import { PagePlaceholder } from '~/components/layout/page-placeholder';

export function meta() {
  return [
    { title: 'Privacy Policy | Multiscale Model Portal | MISM' },
    {
      name: 'description',
      content:
        'Multiscale Immune Systems Modeling - Multiscale Model Portal - Privacy policy',
    },
  ];
}

export default function Privacy() {
  return (
    <PagePlaceholder
      title="Privacy Policy"
      description="Our privacy policy is being finalized. It will cover what the portal stores about your account, uploads, and model runs."
    />
  );
}
