import { getApiErrorMessage } from "@/types/auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "sih26027_token";

// In-flight request cache for deduplication
const inflightRequests = new Map<string, Promise<unknown>>();

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_KEY);
    window.dispatchEvent(new Event("sih26027_token_cleared"));
  }
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(getApiErrorMessage(status, body));
    this.status = status;
    this.body = body;
  }
}

function getRequestKey(path: string, options: RequestInit = {}): string {
  const method = options.method || "GET";
  const body = options.body ? JSON.stringify(options.body) : "";
  return `${method}:${path}:${body}`;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Request deduplication for GET requests
  const isGet = !options.method || options.method === "GET";
  const key = getRequestKey(path, options);
  
  if (isGet && inflightRequests.has(key)) {
    return inflightRequests.get(key) as Promise<T>;
  }

  const requestPromise = (async (): Promise<T> => {
    let res: Response;
    try {
      res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
    } catch {
      throw new ApiError(0, { message: "Unable to connect to the railway service. Please try again." });
    }

    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }

    if (!res.ok) {
      if (res.status === 401) setToken(null);
      throw new ApiError(res.status, body);
    }

    return body as T;
  })();

  if (isGet) inflightRequests.set(key, requestPromise);
  try {
    return await requestPromise;
  } finally {
    if (isGet && inflightRequests.get(key) === requestPromise) {
      inflightRequests.delete(key);
    }
  }
}

export const api = {
  post: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(data) }),
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  put: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(data) }),
  patch: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(data) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export { BASE_URL, TOKEN_KEY };
