import React from 'react';
import styles from './Spinner.module.css';

export const Spinner: React.FC = () => (
  <div className={styles.spinnerWrapper}>
    <div className={styles.spinner} />
  </div>
);