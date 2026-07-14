import { Card, CardBody } from '@heroui/react';
import {
  ArrowPathIcon,
  ChartBarIcon,
  CheckCircleIcon,
  CubeIcon,
  DocumentArrowDownIcon,
} from '@heroicons/react/24/outline';
import { Link } from 'react-router';

import type { UserRunItem } from '~/api/endpoints/runs';
import { deriveStats } from './run-filters';

interface StatCardProps {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  label: string;
  value: string;
  hint?: string;
  accent: string;
  to?: string;
}

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  accent,
  to,
}: StatCardProps) {
  const body = (
    <CardBody className="flex flex-row items-center gap-3 p-4">
      <span
        className={`flex items-center justify-center size-10 rounded-xl shrink-0 ${accent}`}
      >
        <Icon className="size-5" strokeWidth={1.75} aria-hidden="true" />
      </span>
      <div className="flex flex-col min-w-0">
        <span className="text-xl font-extrabold tabular-nums text-default-900 leading-tight truncate">
          {value}
        </span>
        <span className="text-[12px] font-medium text-default-600 truncate">
          {hint ?? label}
        </span>
      </div>
    </CardBody>
  );

  const className =
    'border border-default-200 rounded-2xl transition-colors duration-200';

  if (to) {
    return (
      <Card
        as={Link}
        to={to}
        shadow="none"
        isPressable
        className={`${className} hover:border-primary/50 hover:bg-primary/2`}
      >
        {body}
      </Card>
    );
  }

  return (
    <Card shadow="none" className={className}>
      {body}
    </Card>
  );
}

/**
 * At-a-glance stats over the full (unfiltered) run list. Turns the header's
 * dead space into a small dashboard. Rendered by the parent only when there
 * are enough runs to be worth summarizing.
 */
export function RunsStats({ runs }: { runs: UserRunItem[] }) {
  const stats = deriveStats(runs);

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-8">
      <StatCard
        icon={ChartBarIcon}
        label="Total runs"
        value={String(stats.total)}
        hint={`Total ${stats.total === 1 ? 'run' : 'runs'}`}
        accent="bg-default-100 text-default-700"
      />
      <StatCard
        icon={ArrowPathIcon}
        label="Running now"
        value={String(stats.running)}
        hint="Running now"
        accent="bg-secondary-100 text-secondary-600"
        to={stats.running > 0 ? '/runs?status=running' : undefined}
      />
      <StatCard
        icon={CheckCircleIcon}
        label="Success rate"
        value={stats.successRate === null ? '—' : `${stats.successRate}%`}
        hint="Success rate"
        accent="bg-success-100 text-success-700"
      />
      <StatCard
        icon={DocumentArrowDownIcon}
        label="Outputs produced"
        value={String(stats.outputs)}
        hint="Outputs produced"
        accent="bg-primary-100 text-primary-600"
      />
      <StatCard
        icon={CubeIcon}
        label="Most-run model"
        value={stats.topModel ? String(stats.topModel.count) : '—'}
        hint={stats.topModel ? stats.topModel.name : 'Most-run model'}
        accent="bg-warning-100 text-warning-700"
      />
    </div>
  );
}
