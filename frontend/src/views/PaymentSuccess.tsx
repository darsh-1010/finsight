import { useRouter } from 'next/navigation';
import React, { useEffect } from 'react';
import { PiCheckCircleDuotone } from 'react-icons/pi';

import { Button } from '@/components/ui/button';

const PaymentSuccess: React.FC = () => {
  const navigate = useRouter().push;

  useEffect(() => {
    sessionStorage.removeItem('payment_redirect_pending');
  }, []);

  return (
    <div className="w-full max-w-md">
      <div className="bg-white dark:bg-[#08070A] p-10 rounded-2xl shadow-2xl w-full border border-gray-200 dark:border-gray-800 text-center">
        <div className="flex justify-center mb-6">
          <div className="w-20 h-20 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center">
            <PiCheckCircleDuotone size={48} className="text-green-600 dark:text-green-400" />
          </div>
        </div>
        
        <h2 className="text-3xl font-bold mb-4 text-gray-800 dark:text-white">Payment Successful!</h2>
        <p className="text-gray-600 dark:text-gray-400 mb-8">
          Thank you for your subscription. Your payment has been processed successfully.
          You now have access to your selected tier features.
        </p>
        
        <div className="space-y-3">
          <Button 
            onClick={() => navigate('/dashboard')}
            className="w-full"
          >
            Go to Dashboard
          </Button>
        </div>
      </div>
    </div>
  );
};

export default PaymentSuccess;
