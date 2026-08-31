import { Link as RouterLink } from 'react-router';
import cn from 'classnames';
import { ArrowUpRightIcon, EnvelopeIcon } from '@heroicons/react/16/solid';

import { useUser } from '~/api/auth/user';
import wordmark from './MISM-header-white.svg';

/**
 * TODO(contact): replace with the real project inbox once confirmed.
 * Referenced by the brand column and the "Contact us" support link.
 */
const CONTACT_EMAIL = 'contact@immunescale.org';

const MISM_SITE = 'https://immunescale.org';
const HELX_SITE = 'https://helx.renci.org';

type FooterLink = {
  label: string;
  to: string;
  /** Absolute URL — rendered as an anchor with an outbound affordance. */
  external?: boolean;
};

/**
 * Deliberately omits `/chat` and `/catalog`: the Header's Discover menu points
 * at both, but neither route exists yet, so linking them here would only add
 * more dead ends. Add them once the routes land.
 */
const PORTAL_LINKS: FooterLink[] = [{ label: 'Search', to: '/search' }];

/** `/upload` and `/runs` are `requireUser`-gated, so only link them when signed in. */
const AUTHED_PORTAL_LINKS: FooterLink[] = [
  { label: 'Contribute a Model', to: '/upload' },
  { label: 'My Runs', to: '/runs' },
];

const INFO_LINKS: FooterLink[] = [
  { label: 'About', to: '/about' },
  { label: 'FAQ', to: '/faq' },
  { label: 'User Support', to: '/support' },
  { label: 'Contact Us', to: `mailto:${CONTACT_EMAIL}`, external: true },
];

const MISM_LINKS: FooterLink[] = [
  { label: 'Home', to: MISM_SITE, external: true },
  { label: 'About MISM', to: `${MISM_SITE}/about-us`, external: true },
  {
    label: 'Research',
    to: `${MISM_SITE}/research-and-outreach/our-research/`,
    external: true,
  },
  { label: 'Community', to: `${MISM_SITE}/our-community`, external: true },
];

const linkClassNames = cn(
  'group/link inline-flex items-center gap-1 text-sm text-slate-300',
  'transition-colors duration-200 hover:text-white',
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-success',
  'rounded-xs'
);

function FooterLinkItem({ label, to, external }: FooterLink) {
  return (
    <li>
      {external ? (
        <a
          href={to}
          className={linkClassNames}
          // mailto: links stay in the current tab; http(s) links open a new one.
          {...(to.startsWith('mailto:')
            ? {}
            : { target: '_blank', rel: 'noreferrer' })}
        >
          {label}
          {!to.startsWith('mailto:') && (
            <ArrowUpRightIcon
              aria-hidden
              className={cn(
                'size-3 text-slate-500 transition-all duration-200',
                'group-hover/link:text-success',
                'group-hover/link:-translate-y-px group-hover/link:translate-x-px'
              )}
            />
          )}
        </a>
      ) : (
        <RouterLink to={to} className={linkClassNames}>
          {label}
        </RouterLink>
      )}
    </li>
  );
}

function FooterColumn({
  heading,
  links,
}: {
  heading: string;
  links: FooterLink[];
}) {
  return (
    <nav aria-label={heading}>
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-success">
        {heading}
      </h2>
      <ul className="mt-4 flex flex-col gap-2.5">
        {links.map((link) => (
          <FooterLinkItem key={link.label} {...link} />
        ))}
      </ul>
    </nav>
  );
}

export function Footer() {
  const { user } = useUser();
  const year = new Date().getFullYear();

  const portalLinks = user
    ? [...PORTAL_LINKS, ...AUTHED_PORTAL_LINKS]
    : PORTAL_LINKS;

  return (
    <footer
      className={cn(
        'relative w-full text-white',
        // Mirrors the Header's gradient direction so the two bookend the page.
        'bg-linear-to-l from-[#000f3c] to-[#012169]'
      )}
    >
      {/* Brand seam: lime-to-teal hairline echoing the active-nav underline. */}
      <div aria-hidden className="h-0.5 w-full bg-secondary" />
      {/* Subtle molecular dot texture, matching the brand mark's motif. */}
      <div aria-hidden className="absolute inset-0 biological-mesh" />

      <div className="relative container mx-auto px-8 pt-12 pb-8">
        <div
          className={cn(
            'grid gap-10 gap-y-12',
            'grid-cols-1 sm:grid-cols-2',
            'lg:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))] lg:gap-12'
          )}
        >
          {/* Brand */}
          <div className="flex flex-col gap-4 sm:col-span-2 lg:col-span-1">
            <RouterLink
              to="/"
              className={cn(
                'w-fit rounded-xs',
                'focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-success'
              )}
            >
              <img
                src={wordmark}
                alt="MISM — Multiscale Immune Systems Modeling"
                className="h-11 w-auto"
              />
            </RouterLink>
            <p className="font-headline text-lg font-bold text-white">
              Multiscale Model Portal
            </p>
            <p className="max-w-sm text-sm leading-relaxed text-slate-300/85">
              Research reported on this website is supported by the National Institute of Allergy and Infectious Diseases (NIAID) of the National Institutes of Health under award number U54AI191253. The content is solely the responsibility of the authors and does not necessarily represent the official views of the National Institutes of Health.
            </p>
            {/* <a
              href={`mailto:${CONTACT_EMAIL}`}
              className={cn(linkClassNames, 'mt-1')}
            >
              <EnvelopeIcon
                aria-hidden
                className="size-4 text-slate-500 transition-colors duration-200 group-hover/link:text-success"
              />
              {CONTACT_EMAIL}
            </a> */}
          </div>

          <FooterColumn heading="Models & Data" links={portalLinks} />
          <FooterColumn heading="Info" links={INFO_LINKS} />
          <FooterColumn heading="MISM" links={MISM_LINKS} />
        </div>

        {/* Disclaimers */}
        <div
          className={cn(
            'mt-12 flex flex-col-reverse gap-4 border-t border-white/10 pt-6',
            'sm:flex-row sm:items-center sm:justify-between'
          )}
        >
          <p className="text-xs text-slate-300/85">
            © {year} Multiscale Immune Systems Modeling. All rights reserved.
          </p>
          <RouterLink
            to="/privacy"
            className={cn(linkClassNames, 'text-xs whitespace-nowrap')}
          >
            Privacy Policy
          </RouterLink>
        </div>
      </div>
    </footer>
  );
}
