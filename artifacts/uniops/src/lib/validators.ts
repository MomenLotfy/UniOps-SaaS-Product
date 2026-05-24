export const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
export const URL_REGEX = /^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_+.~#?&//=]*)$/;
export const DOMAIN_REGEX = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$/;
export const IP_REGEX = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
export const ARN_REGEX = /^arn:aws:[a-zA-Z0-9-]+:[a-z0-9-]*:\d{12}:.+$/;

export function validateEmail(email: string): string | null {
  if (!email) return 'Email is required';
  if (!EMAIL_REGEX.test(email)) return 'Enter a valid email address';
  return null;
}

export function validatePassword(password: string): string | null {
  if (!password) return 'Password is required';
  if (password.length < 8) return 'Password must be at least 8 characters';
  if (!/[A-Z]/.test(password)) return 'Include at least one uppercase letter';
  if (!/[a-z]/.test(password)) return 'Include at least one lowercase letter';
  if (!/\d/.test(password)) return 'Include at least one number';
  if (!/[@$!%*?&]/.test(password)) return 'Include at least one special character (@$!%*?&)';
  return null;
}

export function validateRequired(value: string, label = 'This field'): string | null {
  if (!value?.trim()) return `${label} is required`;
  return null;
}

export function validateUrl(url: string): string | null {
  if (!url) return 'URL is required';
  if (!URL_REGEX.test(url)) return 'Enter a valid URL (must start with https://)';
  return null;
}

export function validateDomain(domain: string): string | null {
  if (!domain) return 'Domain is required';
  if (!DOMAIN_REGEX.test(domain)) return 'Enter a valid domain (e.g. company.com)';
  return null;
}

export function validateArn(arn: string): string | null {
  if (!arn) return 'ARN is required';
  if (!ARN_REGEX.test(arn)) return 'Enter a valid AWS ARN';
  return null;
}

export type FormErrors<T> = Partial<Record<keyof T, string>>;

export function hasErrors<T>(errors: FormErrors<T>): boolean {
  return Object.values(errors).some(Boolean);
}
