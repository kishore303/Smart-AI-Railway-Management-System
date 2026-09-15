import React from "react";
import Link from "next/link";
import GovHeader from "@/components/GovHeader";

export default function NotFoundPage() {
  return (
    <>
      <GovHeader />
      <main className="gov-page" style={{ maxWidth: 600, margin: "0 auto", padding: "48px 32px", textAlign: "center" }}>
        <h1 className="gov-title" style={{ fontSize: 48, marginBottom: 8 }}>404</h1>
        <p style={{ fontSize: 18, color: "var(--text-secondary)", marginBottom: 24 }}>
          The requested page was not found.
        </p>
        <Link className="gov-btn" href="/dashboard">
          Return to Dashboard
        </Link>
      </main>
    </>
  );
}
