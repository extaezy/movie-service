import React from 'react';
import styles from './EmptyState.module.css';

interface EmptyStateProps {
  message: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ message }) => (
  <div className={styles.empty}>
    <p>{message}</p>
  </div>
);