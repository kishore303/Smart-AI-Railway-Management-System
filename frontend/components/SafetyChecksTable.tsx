"use client";

import React from "react";
import type { SafetyCheck } from "@/types/safety";
import { checkBadgeKind } from "@/types/safety";

export default function SafetyChecksTable({ checks }: { checks: SafetyCheck[] | null }) {
  if (!checks || checks.length === 0) {
    return <div className="gov-empty"><p>No safety checks recorded.</p></div>;
  }
  return (
    <div className="gov-table-wrap">
      <table className="gov-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Check</th>
            <th>Result</th>
            <th>Severity</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((c, i) => (
            <tr key={`${c.check}-${i}`}>
              <td>{i + 1}</td>
              <td>{c.check}</td>
              <td>
                <span className={`gov-badge gov-badge-${checkBadgeKind(c.status)}`}>{c.status}</span>
              </td>
              <td>{c.severity}</td>
              <td>
                {c.reason}
                {c.warning ? <span className="gov-muted"> — Warning: {c.warning}</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
