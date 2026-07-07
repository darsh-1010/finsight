import React from 'react';

import { Button } from '@/components/ui/button';

interface PricingErrorProps {
  error: string;
}

const PricingError: React.FC<PricingErrorProps> = ({ error }) => (
  <div className="flex items-center justify-center min-h-[calc(100vh-80px)] px-4">
    <div className="text-center">
      <h2 className="text-2xl font-semibold mb-4 text-red-500">{error}</h2>
      <Button onClick={() => window.location.reload()}>Retry</Button>
    </div>
  </div>
);

export default PricingError;
