import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import './ErrorBoundary.css';

interface Props {
  children: ReactNode;
  fallback?: (error: Error, resetError: () => void) => ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * 全局错误边界
 * 捕获子组件树中的错误，防止整个应用崩溃
 */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  resetError = (): void => {
    this.setState({ hasError: false, error: null });
  };

  override render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.resetError);
      }

      return (
        <div className="error-boundary-fallback">
          <div className="error-boundary-card">
            <div className="error-boundary-icon">
              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h2 className="error-boundary-title">出现了一些问题</h2>
            <p className="error-boundary-message">{this.state.error.message}</p>
            <div className="error-boundary-actions">
              <button className="error-boundary-btn primary" onClick={this.resetError}>
                重试
              </button>
              <button
                className="error-boundary-btn secondary"
                onClick={() => {
                  window.location.href = '/config';
                }}
              >
                打开配置
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
