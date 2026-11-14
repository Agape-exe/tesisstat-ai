import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo);
  }

  public override render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem',
            fontFamily: "'Segoe UI', system-ui, sans-serif",
            backgroundColor: '#fafafd',
            color: '#1e293b',
          }}
        >
          <div
            style={{
              maxWidth: '520px',
              width: '100%',
              backgroundColor: '#ffffff',
              borderRadius: '12px',
              padding: '2rem',
              boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)',
              border: '1px solid #e2e8f0',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                backgroundColor: '#fee2e2',
                color: '#dc2626',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '24px',
                margin: '0 auto 1rem',
              }}
            >
              ⚠
            </div>
            <h1
              style={{
                fontSize: '1.25rem',
                margin: '0 0 0.5rem',
                fontWeight: 600,
              }}
            >
              Se produjo un error al cargar la aplicación
            </h1>
            <p
              style={{
                color: '#64748b',
                fontSize: '0.9rem',
                marginBottom: '1.5rem',
              }}
            >
              {this.state.error?.message ||
                'Error inesperado durante el renderizado.'}
            </p>
            <div
              style={{
                display: 'flex',
                gap: '0.75rem',
                justifyContent: 'center',
              }}
            >
              <button
                type="button"
                onClick={() => window.location.reload()}
                style={{
                  padding: '0.6rem 1.2rem',
                  backgroundColor: '#4f46e5',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Recargar página
              </button>
              <button
                type="button"
                onClick={() => {
                  window.location.hash = '';
                  window.location.reload();
                }}
                style={{
                  padding: '0.6rem 1.2rem',
                  backgroundColor: '#f1f5f9',
                  color: '#475569',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                Ir a Investigaciones
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
