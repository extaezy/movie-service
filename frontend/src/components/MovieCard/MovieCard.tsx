import React from 'react';
import { Link } from 'react-router-dom';
import type { Movie } from '../../types';
import styles from './MovieCard.module.css';

interface MovieCardProps {
  movie: Movie;
  onToggleFavorite?: (id: string, e: React.MouseEvent) => void;
}

export const MovieCard: React.FC<MovieCardProps> = ({ movie, onToggleFavorite }) => {
  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onToggleFavorite?.(movie.id, e);
  };

  return (
    <Link to={`/movies/${movie.id}`} className={styles.card}>
      <div className={styles.posterWrapper}>
        <img src={movie.poster_url || '/placeholder.png'} alt={movie.title} className={styles.poster} />
        <button
          className={`${styles.favoriteBtn} ${movie.is_favorite ? styles.active : ''}`}
          onClick={handleFavoriteClick}
          title={movie.is_favorite ? 'Удалить из избранного' : 'Добавить в избранное'}
        >
          ★
        </button>
      </div>
      <div className={styles.info}>
        <h3 className={styles.title} title={movie.title}>{movie.title}</h3>
        <span className={styles.year}>{movie.year}</span>
      </div>
    </Link>
  );
};