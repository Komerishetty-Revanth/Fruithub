import { API_BASE } from "../config.js";
import { clearSession, getToken } from "../auth/session.js";

export class ApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

// Every API call in the app goes through this function.
export async function request(path, { method = "GET", body, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(API_BASE + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("NETWORK", "Cannot reach the server. Please check that the backend is running.", 0);
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }

  if (!res.ok) {
    if (res.status === 401 && auth && token) clearSession(); // expired or invalid session
    const err = data && data.error;
    throw new ApiError(
      (err && err.code) || "ERROR",
      (err && err.message) || "Something went wrong. Please try again.",
      res.status
    );
  }
  return data;
}