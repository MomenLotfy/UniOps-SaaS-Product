import type { ApiError } from '@/types/api';

export class AppError extends Error {
  code: string;
  status: number;
  details?: Record<string, string[]>;

  constructor(message: string, code = 'UNKNOWN_ERROR', status = 500, details?: Record<string, string[]>) {
    super(message);
    this.name = 'AppError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function parseApiError(error: unknown): AppError {
  if (error instanceof AppError) return error;

  if (typeof error === 'object' && error !== null) {
    const e = error as { response?: { data?: ApiError; status?: number }; message?: string };
    if (e.response?.data) {
      const { message, code, status, details } = e.response.data;
      return new AppError(message, code, status, details);
    }
    if (e.message) return new AppError(e.message);
  }

  return new AppError('An unexpected error occurred');
}

export function getFieldError(error: AppError | null, field: string): string | undefined {
  return error?.details?.[field]?.[0];
}

export const ERROR_MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: 'Invalid email or password.',
  EMAIL_TAKEN: 'This email is already registered.',
  UNAUTHORIZED: 'You are not authorized to perform this action.',
  SESSION_EXPIRED: 'Your session has expired. Please log in again.',
  RATE_LIMITED: 'Too many requests. Please wait a moment and try again.',
  NETWORK_ERROR: 'Network error. Check your connection.',
  SERVER_ERROR: 'Server error. Our team has been notified.',
  EMAIL_NOT_VERIFIED: 'Please verify your email address first.',
  TWO_FACTOR_REQUIRED: 'Two-factor authentication is required.',
};
