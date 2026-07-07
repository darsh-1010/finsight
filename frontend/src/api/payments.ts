import client from './client';

export interface PreviewSubscriptionResponse {
  upcoming_invoice_total: number;
  proration_date: number;
  unused_credit_balance: number;
  credit_applied_today: number;
  currency: string;
  amount_due_today: number;
  next_billing_date: number;
  new_total: number;
  is_yearly_to_monthly: boolean;
  is_downgrade: boolean;
}

export const createCheckoutSession = async (priceId: string, successUrl: string, cancelUrl: string) => {
  const response = await client.post(
    '/payments/create-checkout-session',
    {
      price_id: priceId,
      success_url: successUrl,
      cancel_url: cancelUrl,
    },
    {
      withCredentials: true,
    }
  );

  return response.data;
};

export const updateSubscription = async (priceId: string) => {
  return { status: 'success', priceId };
};

export const cancelSubscription = async () => {
  return { status: 'success' };
};

export const previewSubscriptionUpdate = async (_priceId: string): Promise<PreviewSubscriptionResponse> => {
  return {
    upcoming_invoice_total: 0,
    proration_date: Date.now() / 1000,
    unused_credit_balance: 0,
    credit_applied_today: 0,
    currency: 'usd',
    amount_due_today: 0,
    next_billing_date: Date.now() / 1000,
    new_total: 0,
    is_yearly_to_monthly: false,
    is_downgrade: false,
  };
};

export const createPortalSession = async (returnUrl: string) => {
  return { portal_url: returnUrl };
};
