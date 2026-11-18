import React from 'react';
import { Link } from 'react-router-dom';
import type { Movie } from '../../types';
import styles from './MovieCard.module.css';

interface MovieCardProps {
  movie: Pick<Movie, 'id' | 'title' | 'poster_url' | 'is_favorite'> & { year?: number };
  to: string;
  onToggleFavorite?: (id: string, e: React.MouseEvent) => void;
}

export const MovieCard: React.FC<MovieCardProps> = ({ movie, to, onToggleFavorite }) => {
  // Переключение избранного
  const handleFavoriteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onToggleFavorite?.(movie.id, e);
  };

  return (
    <Link to={to} className={styles.card}>
      <div className={styles.posterWrapper}>
        {movie.poster_url && (
          <img
            key={movie.poster_url}
            src={movie.poster_url}
            alt={movie.title}
            className={styles.poster}
            loading="lazy"
            onError={(event) => { event.currentTarget.hidden = true; }}
          />
        )}
        <button
          type="button"
          className={`${styles.favoriteBtn} ${movie.is_favorite ? styles.active : ''}`}
          onClick={handleFavoriteClick}
          disabled={!onToggleFavorite}
          title={movie.is_favorite ? 'Удалить из избранного' : 'Добавить в избранное'}
        >
          ★
        </button>
      </div>
      <div className={styles.info}>
        <h3 className={styles.title} title={movie.title}>{movie.title}</h3>
        {movie.year !== undefined && <span className={styles.year}>{movie.year}</span>}
      </div>
    </Link>
  );
};
