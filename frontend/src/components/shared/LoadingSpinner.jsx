import React from 'react';
import { clsx } from 'clsx';

export default function LoadingSpinner({ size = 'md', className }) {
  const sizeMap = { sm: 'w-4 h-4 border-2', md: 'w-6 h-6 border-2', lg: 'w-10 h-10 border-3' };
  return (
    <div
      className={clsx(
        'rounded-full border-steel border-t-transparent animate-spin',
        sizeMap[size],
        className
      )}
    />
  );
}
