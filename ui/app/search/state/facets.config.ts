import type { FacetWidget, ResourceType } from './types';

export interface FacetConfig {
  /** Stable identifier used in URL params and React keys. */
  id: string;
  /** API field name. Used verbatim in aggs + filters. */
  field: string;
  /** Human label shown in the sidebar. */
  label: string;
  /** Widget renderer + API operator family. */
  widget: FacetWidget;
  /** Which tabs expose this facet. */
  resourceTypes: ResourceType[];
  /**
   * For `terms` widgets only: the operator to send to the API.
   *   - `overlap` when the backend field is a `string[]` — tests whether any
   *     selected value appears in the result's array.
   *   - `in` when the backend field is a scalar `string` — tests whether the
   *     result's single value is in the selected set.
   * Defaults to `overlap` when omitted.
   */
  termsOp?: 'overlap' | 'in';
  /**
   * Optional placeholder / helper hint shown when the facet is empty.
   */
  placeholder?: string;
}

export const FACETS: readonly FacetConfig[] = [
  {
    id: 'model_scales',
    field: 'model_scales',
    label: 'Model Scales',
    widget: 'terms',
    termsOp: 'overlap',
    resourceTypes: ['model', 'dataset'],
  },
  {
    id: 'organisms',
    field: 'organisms',
    label: 'Organisms',
    widget: 'terms',
    termsOp: 'overlap',
    resourceTypes: ['model', 'dataset'],
  },
  {
    id: 'domains',
    field: 'domains',
    label: 'Domains',
    widget: 'terms',
    termsOp: 'overlap',
    resourceTypes: ['model', 'dataset'],
  },
  {
    id: 'format_tags',
    field: 'format_tags',
    label: 'Formats',
    widget: 'terms',
    termsOp: 'overlap',
    resourceTypes: ['dataset'],
  },
  {
    id: 'execution_type',
    field: 'execution_type',
    label: 'Execution Type',
    widget: 'terms',
    termsOp: 'in',
    resourceTypes: ['model'],
  },
  {
    id: 'owner',
    field: 'owner',
    label: 'Owner',
    widget: 'terms',
    termsOp: 'in',
    resourceTypes: ['model', 'dataset'],
  },
  // {
  //   id: 'license',
  //   field: 'license',
  //   label: 'License',
  //   widget: 'terms',
  //   termsOp: 'in',
  //   resourceTypes: ['model', 'dataset'],
  // },
  {
    id: 'created_at',
    field: 'created_at',
    label: 'Created',
    widget: 'range',
    resourceTypes: ['model', 'dataset'],
  },
];

/** Facets visible for a given tab. */
export function facetsForResourceType(
  resourceType: ResourceType
): readonly FacetConfig[] {
  return FACETS.filter((facet) => facet.resourceTypes.includes(resourceType));
}

/** Look up a facet by id. Returns undefined if the id is unknown. */
export function getFacetConfig(id: string): FacetConfig | undefined {
  return FACETS.find((facet) => facet.id === id);
}
