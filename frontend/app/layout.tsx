import React from "react";
import "./globals.css";
import "maplibre-gl/dist/maplibre-gl.css";
import { AuthProvider } from "@/lib/auth-context";
import { NotificationsProvider } from "@/lib/notifications-context";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export const metadata = {
  title: "SIH26027 — Railway Block Planning Portal",
  description: "Indian Railways maintenance decision-support system",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
    apple: "/favicon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ErrorBoundary>
          <AuthProvider>
            <NotificationsProvider>{children}</NotificationsProvider>
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
