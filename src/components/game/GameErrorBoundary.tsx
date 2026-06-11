import { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from '@/design-system/components/Button';
import './GameErrorBoundary.css';

interface Props {
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class GameErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo,
    });

    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    console.error('Game Error Boundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  handleReload = () => {
    window.location.reload();
  };

  handleGoToLobby = () => {
    window.location.href = '/lobby';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="game-error-boundary">
          <div className="game-error-boundary__content">
            <div className="game-error-boundary__icon">⚠️</div>
            <h1 className="game-error-boundary__title">
              Произошла ошибка
            </h1>
            <p className="game-error-boundary__message">
              Что-то пошло не так во время игры. Попробуйте перезагрузить
              страницу или вернуться в лобби.
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="game-error-boundary__details">
                <summary className="game-error-boundary__summary">
                  Технические детали (для разработчиков)
                </summary>
                <div className="game-error-boundary__error-info">
                  <div className="game-error-boundary__error-message">
                    <strong>Ошибка:</strong>
                    <pre>{this.state.error.message}</pre>
                  </div>
                  {this.state.errorInfo && (
                    <div className="game-error-boundary__stack-trace">
                      <strong>Stack Trace:</strong>
                      <pre>{this.state.errorInfo.componentStack}</pre>
                    </div>
                  )}
                </div>
              </details>
            )}

            <div className="game-error-boundary__actions">
              <Button
                variant="primary"
                onClick={this.handleRetry}
                className="game-error-boundary__retry-btn"
              >
                Попробовать снова
              </Button>
              <Button
                variant="secondary"
                onClick={this.handleReload}
                className="game-error-boundary__reload-btn"
              >
                Перезагрузить страницу
              </Button>
              <Button
                variant="ghost"
                onClick={this.handleGoToLobby}
                className="game-error-boundary__lobby-btn"
              >
                Вернуться в лобби
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default GameErrorBoundary;