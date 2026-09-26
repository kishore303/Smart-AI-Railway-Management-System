export interface BackendUserBrief {
  id: number;
  name: string;
  email: string;
  role: string;
  department: string;
  department_id: number;
  is_active: boolean;
  permissions?: string[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: BackendUserBrief;
  expires_in: number;
}

export interface MeResponse extends BackendUserBrief {
  last_login?: string | null;
  created_at?: string | null;
}

export interface ForgotPasswordResponse {
  message: string;
  reset_token?: string | null;
}

export interface ResetPasswordResponse {
  message: string;
}

export interface ApiError {
  detail?: string | Array<{ msg?: string; loc?: unknown }>;
  message?: string;
}

export function getApiErrorMessage(status: number, body: unknown): string {
  // Prefer the backend's specific message when it is a short, display-safe
  // string (e.g. "Block 29 not found"). Array details (FastAPI 422 payloads)
  // fall through to the generic per-status text below.
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as ApiError).detail;
    if (typeof d === "string" && d.length > 0 && d.length < 200) {
      if (d === "Invalid credentials") return "Invalid username or password.";
      if (d === "Account inactive") return "Account is inactive. Please contact the administrator.";
      if (status === 400 || status === 403 || status === 404 || status === 409 || status === 422) return d;
    }
  }
  if (status === 400) return "Invalid request. Please check the entered details.";
  if (status === 401) return "Invalid username or password.";
  if (status === 403) return "You are not authorized to access this resource.";
  if (status === 404) return "Requested resource was not found.";
  if (status === 422) return "Validation failed. Please check the entered details.";
  if (status >= 500) return "Unable to connect to the railway service. Please try again.";
  return "Something went wrong. Please try again.";
}
