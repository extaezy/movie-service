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
            onError={(event) => {
              event.currentTarget.hidden = true;
            }}
          />
        )}
        <button
          type="button"
          className={`${styles.favoriteBtn} ${movie.is_favorite ? styles.active : ''}`}
          onClick={handleFavoriteClick}
          disabled={!onToggleFavorite}
          title={movie.is_favorite ? 'Удалить из избранного' : 'Добавить в избранное'}
          aria-label={movie.is_favorite ? 'Удалить из избранного' : 'Добавить в избранное'}
        >
          <svg
            viewBox="0 0 24 24"
            className={styles.starSvg}
            fill={movie.is_favorite ? 'currentColor' : 'none'}
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        </button>
      </div>
      <div className={styles.info}>
        <h3 className={styles.title} title={movie.title}>
          {movie.title}
        </h3>
        {movie.year !== undefined && <span className={styles.year}>{movie.year}</span>}
      </div>
    </Link>
  );
};