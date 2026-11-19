import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { Movie } from '../../types';
import styles from './MovieCard.module.css';

interface MovieCardProps {
  movie: Movie;
  onToggleFavorite?: (movieId: string) => void;
  onAddToWatchlist?: (movieId: string) => void;
}

export const MovieCard: React.FC<MovieCardProps> = ({
  movie,
  onToggleFavorite,
  onAddToWatchlist,
}) => {
  const navigate = useNavigate();

  const handleBookmarkClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (onAddToWatchlist) {
      onAddToWatchlist(movie.id);
    } else if (onToggleFavorite) {
      onToggleFavorite(movie.id);
    }
  };

  const handleStarClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onToggleFavorite?.(movie.id);
  };

  const displayRating = (movie.imdb_rating || movie.kp_rating || 8.2).toFixed(1);

  return (
    <div className={styles.card}>
      <div className={styles.posterWrapper}>
        <Link to={`/movies/${movie.id}`} className={styles.posterLink}>
          <img
            src={movie.poster_url}
            alt={movie.title}
            className={styles.poster}
            loading="lazy"
          />
        </Link>

        {/* Закладка-лента IMDb в левом верхнем углу */}
        <button
          type="button"
          className={`${styles.ribbonBookmark} ${
            movie.is_watchlist || movie.is_favorite ? styles.ribbonActive : ''
          }`}
          onClick={handleBookmarkClick}
          title="Добавить в список"
        >
          <svg viewBox="0 0 24 34" className={styles.ribbonSvg}>
            <path d="M0 0 H24 V34 L12 26 L0 34 Z" />
          </svg>
          <span className={styles.ribbonIcon}>
            {movie.is_watchlist || movie.is_favorite ? '✓' : '+'}
          </span>
        </button>
      </div>

      <div className={styles.body}>
        <div className={styles.ratingRow}>
          <span className={styles.imdbRating}>
            <span className={styles.goldStar}>★</span> {displayRating}
          </span>
          <button
            type="button"
            className={`${styles.rateStarBtn} ${
              movie.is_favorite ? styles.rateStarActive : ''
            }`}
            onClick={handleStarClick}
            title="В избранное / Оценить"
          >
            {movie.is_favorite ? '★' : '☆'}
          </button>
        </div>

        <Link to={`/movies/${movie.id}`} className={styles.title} title={movie.title}>
          {movie.title}
        </Link>

        <button
          type="button"
          className={`${styles.primaryPillBtn} ${
            movie.is_watchlist ? styles.primaryPillBtnAdded : ''
          }`}
          onClick={handleBookmarkClick}
        >
          {movie.is_watchlist ? '✓ В списке' : '+ В список'}
        </button>

        <div className={styles.footerActions}>
          <button
            type="button"
            className={styles.trailerBtn}
            onClick={() => navigate(`/movies/${movie.id}`)}
          >
            <span>▶</span> Трейлер
          </button>
          <Link
            to={`/movies/${movie.id}`}
            className={styles.infoBtn}
            title="Подробнее о фильме"
          >
            i
          </Link>
        </div>
      </div>
    </div>
  );
};