import React from "react";
import Link from "next/link";

export default function Breadcrumbs({ trail }: { trail: Array<{ label: string; href?: string }> }) {
  return (
    <nav className="gov-breadcrumbs" aria-label="Breadcrumb">
      {trail.map((t, i) => (
        <span key={t.label}>
          {i > 0 ? " / " : null}
          {t.href ? <Link className="gov-link" href={t.href}>{t.label}</Link> : <span>{t.label}</span>}
        </span>
      ))}
    </nav>
  );
}
