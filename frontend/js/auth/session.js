const KEY = "fh_session";

export function saveSession(token, user) {
  localStorage.setItem(KEY, JSON.stringify({ token, user }));
}

function read() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || null;
  } catch {
    return null;
  }
}

export const getToken = () => read()?.token || null;
export const getUser = () => read()?.user || null;
export const isLoggedIn = () => !!getToken();
export const clearSession = () => localStorage.removeItem(KEY);