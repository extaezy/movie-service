import { isAxiosError } from 'axios';

interface ApiErrorResponse {
  detail?: string | { loc: (string | number)[]; msg: string }[];
}

const fieldLabels: Record<string, string> = {
  identifier: 'Имя пользователя или email',
  username: 'Имя пользователя',
  email: 'Email',
  password: 'Пароль',
  password_confirm: 'Подтверждение пароля',
};

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  if (!isAxiosError<ApiErrorResponse>(error)) return fallback;

  if (!error.response || error.response.status >= 500) {
    return 'Сервис временно недоступен. Попробуйте позже.';
  }

  const detail = error.response.data?.detail;
  if (typeof detail === 'string') return detail || fallback;

  if (Array.isArray(detail)) {
    return detail.map(({ loc, msg }) => {
      const fieldLabel = fieldLabels[String(loc[1])];
      return fieldLabel ? `${fieldLabel}: ${msg}` : msg;
    }).join(' ') || fallback;
  }

  return fallback;
};
