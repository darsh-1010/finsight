import client from "./client";
import axios from "axios";

export interface User {
  id: number;
  email: string;
  role: string;
  tier_level: number;
  tier_name: string;
  entitlements?: string[];
  is_onboarded: boolean;
  is_verified: boolean;
  experience_level?: string;
  risk_level?: string;
  updated_at?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface SignupCredentials {
  email: string;
  password: string;
  role_id: number;
  tier_level?: number;
}

export interface ChangePasswordCredentials {
  current_password: string;
  new_password: string;
}

export interface ForgotPasswordCredentials {
  email: string;
}

export interface ResetPasswordCredentials {
  token: string;
  new_password: string;
}

export interface AuthResponse {
  message: string;
  user_id?: number;
}

export interface VisitingUser {
  id: number;
  email: string;
  chat_count: number;
}

export interface Question {
  id: number;
  tier_id: string;
  question_text: string;
  question_description: string;
  options: {
    id?: number | string;
    label?: string;
    value?: string;
    text?: string;
    name?: string;
  }[];
  title: string;
  question_type: string;
  order: number;
  validation_rules: string;
}

export interface AnswerCreate {
  question_id: number;
  option_id: number | null;
  answer_value: string;
}

export const authApi = {
  signup: async (data: SignupCredentials): Promise<AuthResponse> => {
    const response = await client.post("/auth/signup", data);

    return response.data;
  },

  login: async (data: LoginCredentials): Promise<AuthResponse> => {
    const response = await client.post("/auth/login", data);

    return response.data;
  },

  logout: async (): Promise<AuthResponse> => {
    const response = await client.get("/auth/logout");

    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await client.get("/auth/me");
    if (typeof response.data !== 'object' || !response.data || !('id' in response.data)) {
      throw new Error("Invalid user data received. API may be misconfigured.");
    }
    return response.data;
  },

  refreshToken: async (): Promise<void> => {
    await client.get("/auth/refresh");
  },

  changePassword: async (
    data: ChangePasswordCredentials,
  ): Promise<AuthResponse> => {
    const response = await client.post("/auth/change-password", data);

    return response.data;
  },

  forgotPassword: async (data: ForgotPasswordCredentials): Promise<AuthResponse> => {
    const response = await client.post("/auth/forgot-password", data);
    return response.data;
  },

  resetPassword: async (data: ResetPasswordCredentials): Promise<AuthResponse> => {
    const response = await client.post("/auth/reset-password", data);
    return response.data;
  },

  resendVerification: async (): Promise<AuthResponse> => {
    const response = await client.post("/auth/resend-verification");
    return response.data;
  },

  verifyEmail: async (token: string): Promise<AuthResponse> => {
    const response = await client.get(`/auth/verify-email?token=${token}`);
    return response.data;
  },
};

export const visitingUsersApi = {
  /**
   * POST /auth/visiting-users
   * - 201: new visiting user created
   * - 200: returning visiting user found
   * - 400 with detail "You already have an account. Please login.": registered user
   */
  register: async (email: string): Promise<VisitingUser> => {
    const response = await client.post("/auth/visiting-users", { email });
    return response.data;
  },

  /**
   * PATCH /auth/visiting-users/{id}/chat-count
   * Updates the chat_count for the visiting user after each bot response.
   */
  updateChatCount: async (id: number, chat_count: number): Promise<VisitingUser> => {
    const response = await client.patch(
      `/auth/visiting-users/${id}/chat-count`,
      { chat_count }
    );
    return response.data;
  },
};

/** Cookie name — configurable via VITE_VISITING_USER_COOKIE_NAME env variable */
const VISITING_USER_COOKIE_NAME: string =
  (process.env.VITE_VISITING_USER_COOKIE_NAME as string | undefined) ??
  "finsight_visiting_user";

/** Visiting user cookie expires after 4 hours */
const COOKIE_EXPIRY_HOURS = 4;

export const getStoredVisitingUser = (): VisitingUser | null => {
  try {
    const match = document.cookie
      .split("; ")
      .find((row) => row.startsWith(`${VISITING_USER_COOKIE_NAME}=`));
    if (!match) return null;
    const raw = decodeURIComponent(match.split("=").slice(1).join("="));
    return JSON.parse(raw) as VisitingUser;
  } catch {
    return null;
  }
};

export const storeVisitingUser = (user: VisitingUser): void => {
  const expires = new Date();
  expires.setTime(expires.getTime() + COOKIE_EXPIRY_HOURS * 60 * 60 * 1000);
  document.cookie = [
    `${VISITING_USER_COOKIE_NAME}=${encodeURIComponent(JSON.stringify(user))}`,
    `expires=${expires.toUTCString()}`,
    "path=/",
    "SameSite=Lax",
  ].join("; ");
};

export const clearVisitingUser = (): void => {
  // Expire the cookie immediately
  document.cookie = [
    `${VISITING_USER_COOKIE_NAME}=`,
    "expires=Thu, 01 Jan 1970 00:00:00 UTC",
    "path=/",
    "SameSite=Lax",
  ].join("; ");
  // Clean up any legacy localStorage keys
};

/** Whether an axios error carries the "already has account" message */
export const isRegisteredUserError = (error: unknown): boolean => {
  if (axios.isAxiosError(error)) {
    return (
      error.response?.status === 400 &&
      typeof error.response?.data?.detail === "string" &&
      error.response.data.detail.toLowerCase().includes("already have an account")
    );
  }
  return false;
};

/* Onboarding */

export const OnboardingApi = {
  fetchQuestions: async (): Promise<Question[]> => {
    const response = await client.get("/onboarding/questions");

    return response.data;
  },
  submitOnboarding: async (answers: AnswerCreate[]): Promise<void> => {
    await client.post("/onboarding/answers", answers);
  },
};
