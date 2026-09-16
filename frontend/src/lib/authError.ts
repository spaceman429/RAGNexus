const UNAUTHORIZED_MESSAGE =
  "API Key 无效或未配置，请检查 frontend/.env 中的 API_KEY";

type AuthErrorListener = (message: string | null) => void;

const listeners = new Set<AuthErrorListener>();

export function subscribeAuthError(listener: AuthErrorListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function notifyAuthError(message = UNAUTHORIZED_MESSAGE) {
  console.error(message);
  listeners.forEach((listener) => listener(message));
}

export function clearAuthError() {
  listeners.forEach((listener) => listener(null));
}
