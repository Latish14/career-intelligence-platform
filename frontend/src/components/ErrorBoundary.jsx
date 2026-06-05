import { Component } from "react";

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("Report render error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="card alert--error" role="alert" style={{ marginTop: "1.5rem" }}>
          <h3 className="card__title">Something went wrong displaying your report</h3>
          <p className="card__subtitle" style={{ marginTop: "0.5rem" }}>
            {this.state.error?.message || "An unexpected error occurred."}
          </p>
          {this.props.onReset && (
            <button
              type="button"
              className="btn btn--ghost"
              style={{ marginTop: "1rem" }}
              onClick={this.props.onReset}
            >
              Try again
            </button>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
