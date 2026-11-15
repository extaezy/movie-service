import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Spinner } from '../../components/Spinner/Spinner';
import { EmptyState } from '../../components/EmptyState/EmptyState';
import { ErrorState } from '../../components/ErrorState/ErrorState';
import { useToast } from '../../context/ToastContext';
import {
  getFriendsApi,
  getIncomingRequestsApi,
  acceptFriendRequestApi,
  declineFriendRequestApi,
  removeFriendApi,
} from '../../api/friends';
import type { FriendRequest } from '../../api/friends';
import type { User } from '../../types';
import styles from './Friends.module.css';

export const Friends: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'friends' | 'requests'>('friends');
  const [friends, setFriends] = useState<User[]>([]);
  const [requests, setRequests] = useState<FriendRequest[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<boolean>(false);

  const { showToast } = useToast();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const [friendsData, requestsData] = await Promise.all([
        getFriendsApi(),
        getIncomingRequestsApi(),
      ]);
      setFriends(friendsData);
      setRequests(requestsData);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRemoveFriend = async (e: React.MouseEvent, username: string) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await removeFriendApi(username);
      setFriends((prev) => prev.filter((f) => f.username !== username));
      showToast('Пользователь удалён из друзей');
    } catch {
      showToast('Не удалось удалить из друзей');
    }
  };

  const handleAccept = async (e: React.MouseEvent, req: FriendRequest) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await acceptFriendRequestApi(req.id);
      setRequests((prev) => prev.filter((r) => r.id !== req.id));
      setFriends((prev) => [...prev, req.sender]);
      showToast('Заявка принята');
    } catch {
      showToast('Не удалось принять заявку');
    }
  };

  const handleDecline = async (e: React.MouseEvent, requestId: string) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await declineFriendRequestApi(requestId);
      setRequests((prev) => prev.filter((r) => r.id !== requestId));
      showToast('Заявка отклонена');
    } catch {
      showToast('Не удалось отклонить заявку');
    }
  };

  return (
    <div className={styles.container}>
      {/* Табы */}
      <div className={styles.tabsBar}>
        <button
          className={`${styles.tabBtn} ${activeTab === 'friends' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('friends')}
        >
          Мои друзья ({friends.length})
        </button>
        <button
          className={`${styles.tabBtn} ${activeTab === 'requests' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('requests')}
        >
          Входящие заявки {requests.length > 0 && `(${requests.length})`}
        </button>
      </div>

      {loading ? (
        <Spinner />
      ) : error ? (
        <ErrorState onRetry={fetchData} />
      ) : activeTab === 'friends' ? (
        friends.length === 0 ? (
          <EmptyState message="У вас пока нет друзей" />
        ) : (
          <div className={styles.list}>
            {friends.map((friend) => (
              <Link
                key={friend.id}
                to={`/profile/${friend.username}`}
                className={styles.userCard}
              >
                <img
                  src={friend.avatar_url || 'https://via.placeholder.com/48'}
                  alt={friend.username}
                  className={styles.avatar}
                />
                <div className={styles.userInfo}>
                  <span className={styles.displayName}>
                    {friend.display_name || friend.username}
                  </span>
                  <span className={styles.username}>@{friend.username}</span>
                </div>
                <button
                  className={styles.outlineBtn}
                  onClick={(e) => handleRemoveFriend(e, friend.username)}
                >
                  Удалить из друзей
                </button>
              </Link>
            ))}
          </div>
        )
      ) : requests.length === 0 ? (
        <EmptyState message="Нет входящих заявок" />
      ) : (
        <div className={styles.list}>
          {requests.map((req) => (
            <Link
              key={req.id}
              to={`/profile/${req.sender.username}`}
              className={styles.userCard}
            >
              <img
                src={req.sender.avatar_url || 'https://via.placeholder.com/48'}
                alt={req.sender.username}
                className={styles.avatar}
              />
              <div className={styles.userInfo}>
                <span className={styles.displayName}>
                  {req.sender.display_name || req.sender.username}
                </span>
                <span className={styles.username}>@{req.sender.username}</span>
              </div>
              <div className={styles.actions}>
                <button
                  className={styles.primaryBtn}
                  onClick={(e) => handleAccept(e, req)}
                >
                  Принять
                </button>
                <button
                  className={styles.outlineBtn}
                  onClick={(e) => handleDecline(e, req.id)}
                >
                  Отклонить
                </button>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};