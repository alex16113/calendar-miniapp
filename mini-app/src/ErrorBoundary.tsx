import { Component } from "react";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
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

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: unknown) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 20, textAlign: "center" }}>
          <h2>Что-то пошло не так</h2>
          <p style={{ color: "var(--tg-theme-hint-color)", fontSize: 14 }}>
            {this.state.error?.message || "Неизвестная ошибка"}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="btn"
            style={{ marginTop: 16 }}
          >
            Перезагрузить
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
