/**
 * UNMATCHED Design System - Toast Component
 *
 * Компонент всплывающих уведомлений
 */

import React, { useEffect, useState } from 'react';
import type { ToastProps, ToastOptions } from '../types';

export const Toast: React.FC<ToastProps> = ({
  variant = 'info',
  title,
  message,
  duration = 3000,
  closable = true,
}) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        handleClose();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration]);

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => {
      setIsVisible(false);
    }, 200);
  };

  if (!isVisible) return null;

  const toastIcons: Record<string, string> = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ⓘ',
  };

  return (
    <div className={`toast toast-${variant} ${isExiting ? 'toast-exit' : ''}`}>
      <div className="toast-icon">
        {toastIcons[variant] || 'ⓘ'}
      </div>
      <div className="toast-content">
        {title && <div className="toast-title">{title}</div>}
        <div className="toast-message">{message}</div>
      </div>
      {closable && (
        <button className="toast-close" onClick={handleClose}>
          ✕
        </button>
      )}
    </div>
  );
};

// Toast Container with Context
interface ToastItem extends ToastOptions {
  id: string;
  closable?: boolean;
}

interface ToastContextValue {
  showToast: (options: ToastOptions) => void;
  hideToast: (id: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | undefined>(undefined);

export const useToast = () => {
  const context = React.useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = (options: ToastOptions) => {
    const id = options.id || `toast-${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { ...options, id }]);
    return id;
  };

  const hideToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  return (
    <ToastContext.Provider value={{ showToast, hideToast }}>
      {children}
      <div className="toast-container">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            variant={toast.variant}
            title={toast.title}
            message={toast.message}
            duration={toast.duration}
            closable={toast.closable !== false}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

// Convenience functions for common toast types
export const toast = {
  success: (message: string, title?: string) => ({
    variant: 'success' as const,
    message,
    title,
  }),
  error: (message: string, title?: string) => ({
    variant: 'error' as const,
    message,
    title,
  }),
  warning: (message: string, title?: string) => ({
    variant: 'warning' as const,
    message,
    title,
  }),
  info: (message: string, title?: string) => ({
    variant: 'info' as const,
    message,
    title,
  }),
};

export default Toast;
