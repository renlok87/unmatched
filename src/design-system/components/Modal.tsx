/**
 * UNMATCHED Design System - Modal Component
 *
 * Компонент модального окна
 */

import React, { useEffect } from 'react';
import type { ModalProps, ModalSize } from '../types';
import Button from './Button';

const modalSizes: Record<ModalSize, string> = {
  sm: '400px',
  md: '500px',
  lg: '700px',
  full: '100%',
};

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  size = 'md',
  closable = true,
  children,
}) => {
  // Handle ESC key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && closable) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose, closable]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget && closable) {
      onClose();
    }
  };

  return (
    <div className="modal-backdrop" onClick={handleBackdropClick}>
      <div
        className="modal"
        style={{ maxWidth: modalSizes[size] }}
      >
        {(title || closable) && (
          <div className="modal-header">
            {title && <h3 className="modal-title">{title}</h3>}
            {closable && (
              <button
                className="modal-close"
                onClick={onClose}
                aria-label="Close modal"
              >
                ✕
              </button>
            )}
          </div>
        )}
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  );
};

// Modal with footer
export interface ModalWithFooterProps extends ModalProps {
  footerActions?: Array<{
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary' | 'ghost';
  }>;
}

export const ModalWithFooter: React.FC<ModalWithFooterProps> = ({
  footerActions = [],
  children,
  ...modalProps
}) => {
  return (
    <Modal {...modalProps}>
      {children}
      {footerActions.length > 0 && (
        <div className="modal-footer">
          {footerActions.map((action, index) => (
            <Button
              key={index}
              variant={action.variant || 'secondary'}
              onClick={action.onClick}
            >
              {action.label}
            </Button>
          ))}
        </div>
      )}
    </Modal>
  );
};

export default Modal;
