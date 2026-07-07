export const PROFILE_TAB_IDS = [
  'personal',
  'tokens',
  'subscription',
  'security',
] as const;

export type ProfileTabId = (typeof PROFILE_TAB_IDS)[number];

export const isProfileTab = (value: string | null): value is ProfileTabId =>
  PROFILE_TAB_IDS.includes(value as ProfileTabId);

export const profilePath = (tab: ProfileTabId = 'personal') =>
  tab === 'personal' ? '/user_profile' : `/user_profile?tab=${tab}`;

export const PROFILE_SUBSCRIPTION_PATH = profilePath('subscription');
export const PROFILE_TOKENS_PATH = profilePath('tokens');
