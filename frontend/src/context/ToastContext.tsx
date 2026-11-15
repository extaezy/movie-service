import React, { createContext, useContext, useState, useCallback } from 'react';
import type { ToastMessage } from '../types';
import { Toast } from '../components/Toast/Toast.tsx';

interface ToastContextType {
  showToast: (message: string, actionText?: string, onAction?: () => void) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toast, setToast] = useState<ToastMessage | null>(null);

  const showToast = useCallback((message: string, actionText?: string, onAction?: () => void) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToast({ id, message, actionText, onAction });

    if (!actionText) {
      setTimeout(() => {
        setToast((current) => (current?.id === id ? null : current));
      }, 4000);
    }
  }, []);

  const handleClose = () => {
    setToast(null);
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toast && <Toast toast={toast} onClose={handleClose} />}
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within a ToastProvider');
  return context;
};