import React from "react";

export default function GovHeader({ userLine }: { userLine?: string }) {
  return (
    <header className="gov-header">
      <div className="gov-header-brand">
        <div className="gov-header-emblem" aria-hidden="true">IR</div>
        <div className="gov-header-text">
          <h1>Indian Railways — Block Planning Portal</h1>
          <p>AI-Powered Maintenance Decision Support System</p>
        </div>
      </div>
      <div className="gov-header-right">
        <span className="gov-header-badge">SIH26027</span>
        {userLine ? <span className="gov-header-badge">{userLine}</span> : null}
      </div>
    </header>
  );
}
