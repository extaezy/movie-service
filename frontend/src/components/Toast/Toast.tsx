import React from 'react';
import type { ToastMessage } from '../../types';
import styles from './Toast.module.css';

interface ToastProps {
  toast: ToastMessage;
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({ toast, onClose }) => {
  return (
    <div className={styles.toastContainer}>
      <div className={styles.toast}>
        <span className={styles.icon}>✓</span>
        <span className={styles.message}>{toast.message}</span>
        {toast.actionText && toast.onAction && (
          <button
            className={styles.actionBtn}
            onClick={() => {
              toast.onAction?.();
              onClose();
            }}
          >
            {toast.actionText}
          </button>
        )}
      </div>
    </div>
  );
};