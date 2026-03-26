import { useNavigate } from 'react-router';
import { Button } from '@heroui/react';
import { SparklesIcon } from '@heroicons/react/16/solid';
import cn from 'classnames';

export function AIModeButton() {
  const navigate = useNavigate();

  return (
    <Button
      className={cn(
        'font-semibold text-[13px] transition-all duration-500',
        'h-8 px-3 rounded-full border border-secondary/20',
        // 'bg-linear-to-r from-secondary-100/20 to-success-100/50'
      )}
      color="secondary"
      variant="flat"
      startContent={<SparklesIcon className="size-8" />}
      onPress={() => navigate('/chat')}
    >
      AI Mode
    </Button>
  );
}
