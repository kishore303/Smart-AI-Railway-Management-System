"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="gov-page" style={{ padding: "2rem", textAlign: "center" }}>
          <div className="gov-card" style={{ maxWidth: "600px", margin: "0 auto" }}>
            <div className="gov-error" style={{ padding: "2rem" }}>
              <h2 className="gov-title" style={{ color: "var(--red)", marginBottom: "1rem" }}>
                Something went wrong
              </h2>
              <p className="gov-sub" style={{ marginBottom: "1.5rem" }}>
                An unexpected error occurred. The error has been logged.
              </p>
              <details style={{ textAlign: "left", maxWidth: "500px", margin: "0 auto" }}>
                <summary style={{ cursor: "pointer", marginBottom: "0.5rem" }}>
                  Error details (for debugging)
                </summary>
                <pre style={{ 
                  background: "#f8fafc", 
                  padding: "1rem", 
                  borderRadius: "4px", 
                  overflow: "auto",
                  fontSize: "0.8rem",
                  textAlign: "left"
                }}>
                  {this.state.error?.toString()}
                </pre>
              </details>
              <div style={{ marginTop: "1.5rem", display: "flex", gap: "0.5rem", justifyContent: "center" }}>
                <button 
                  className="gov-btn" 
                  onClick={() => window.location.reload()}
                >
                  Reload Page
                </button>
                <button 
                  className="gov-btn gov-btn-secondary" 
                  onClick={() => {
                    this.setState({ hasError: false, error: null });
                  }}
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}