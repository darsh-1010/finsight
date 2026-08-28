import client from './client';

export const selectTier = async (tierLevel: number) => {
  const response = await client.post(
    '/payments/select-tier',
    { tier_level: tierLevel },
    { withCredentials: true }
  );

  return response.data;
};
