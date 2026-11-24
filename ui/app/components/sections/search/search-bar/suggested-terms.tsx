import { Button } from '@heroui/react';
import cn from 'classnames';

interface SuggestedTermsContainerProps {
  onSelect: (query: string) => void;
}

export function SuggestedTermsContainer({
  onSelect,
}: SuggestedTermsContainerProps) {
  const suggestedTerms = [
    'Cardiac',
    'Pulmonary Fibrosis',
    'Carcinoma',
    'Protein Folding',
  ];

  return (
    <div className="mt-6">
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold text-slate-300 uppercase tracking-widest mr-1">
          Suggested:
        </span>
        {suggestedTerms.map((tag) => (
          <Button
            key={tag}
            variant="solid"
            radius="full"
            size="sm"
            className={cn(
              'h-7 bg-secondary/40 border-1 border-white/10',
              'font-medium text-xs text-white'
            )}
            onPress={() => onSelect(tag)}
          >
            {tag}
          </Button>
        ))}
      </div>
    </div>
  );
}
