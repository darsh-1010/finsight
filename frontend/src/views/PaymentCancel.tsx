import { useRouter } from 'next/navigation';
import React, { useEffect } from 'react';
import { PiXCircleDuotone } from 'react-icons/pi';

import { Button } from '@/components/ui/button';

const PaymentCancel: React.FC = () => {
  const navigate = useRouter().push;

  useEffect(() => {
    sessionStorage.removeItem('payment_redirect_pending');
  }, []);

  return (
    <div className="w-full max-w-md">
      <div className="bg-white dark:bg-[#08070A] p-10 rounded-2xl shadow-2xl w-full border border-gray-200 dark:border-gray-800 text-center">
        <div className="flex justify-center mb-6">
          <div className="w-20 h-20 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center">
            <PiXCircleDuotone size={48} className="text-red-600 dark:text-red-400" />
          </div>
        </div>
        
        <h2 className="text-3xl font-bold mb-4 text-gray-800 dark:text-white">Payment Cancelled</h2>
        <p className="text-gray-600 dark:text-gray-400 mb-8">
          Your payment was cancelled. No charges have been made to your account.
          You can try again whenever you&apos;re ready.
        </p>
        
        <div className="space-y-3">
          <Button 
            onClick={() => navigate('/dashboard')}
            variant="outline"
            className="w-full"
          >
            Go to Dashboard
          </Button>
        </div>
      </div>
    </div>
  );
};

export default PaymentCancel;
