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

// Keep the token, replace the saved user (for example after the phone is verified)
export function updateUser(user) {
  const token = getToken();
  if (token) saveSession(token, user);
}