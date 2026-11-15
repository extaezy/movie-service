import React from 'react';
import styles from './ErrorState.module.css';

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({ message = 'Произошла ошибка при загрузке', onRetry }) => (
  <div className={styles.error}>
    <p>{message}</p>
    {onRetry && (
      <button className={styles.retryBtn} onClick={onRetry}>
        Повторить
      </button>
    )}
  </div>
);