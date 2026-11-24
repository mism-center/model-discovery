import { useEffect, useState } from 'react';
import cn from 'classnames';
import { Input } from '@heroui/react';
import { useDebounce } from 'use-debounce';
import { MagnifyingGlassIcon } from '@heroicons/react/16/solid';

interface FacetSearchInputProps {
  placeholder: string;
  debounce?: number;
  onChange: (value: string) => void;
}

/**
 * Debounced text input used to filter the options within a facet (e.g. a long
 * list of model names). Presentational and search-agnostic — shared by the
 * search sidebar and the runs sidebar.
 */
export function FacetSearchInput({
  placeholder,
  onChange,
  debounce = 100,
}: FacetSearchInputProps) {
  const [search, setSearch] = useState('');
  const [debouncedSearch] = useDebounce(search, debounce);

  useEffect(() => {
    onChange(debouncedSearch);
  }, [debouncedSearch, onChange]);

  return (
    <Input
      classNames={{
        input: 'text-[13px]',
        inputWrapper: cn(
          'min-h-8 h-8 mb-2',
          'bg-white! border border-default-300 shadow-none rounded-md',
          'hover:border-default-500',
          'focus-within:border-default-600! focus-within:ring-2 focus-within:ring-default-200',
          'transition-all duration-200'
        ),
      }}
      radius="none"
      value={search}
      onValueChange={setSearch}
      placeholder={placeholder}
      startContent={
        <MagnifyingGlassIcon className="size-4 text-slate-400 mr-1" />
      }
    />
  );
}
