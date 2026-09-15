import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Auth is handled client-side by ProtectedRoute.tsx + auth-context.tsx.
// The token lives in localStorage (not cookies), so Next.js middleware
// cannot read it. ProtectedRoute redirects unauthenticated users to /login.
// The api-client handles 401 responses by clearing the token.

export function middleware(_request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: [],
};
