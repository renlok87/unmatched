import React, { useState, useRef } from 'react';
import { useMutation, gql } from '@apollo/client';
import { Modal } from '@/design-system/components/Modal';
import { Input } from '@/design-system/components/Input';
import { Button } from '@/design-system/components/Button';
import './EditProfileModal.css';

const UPDATE_PROFILE = gql`
  mutation UpdateProfile($input: UpdateProfileInput!) {
    updateProfile(input: $input) {
      user {
        id
        username
        avatar
        country
        bio
      }
    }
  }
`;

interface EditProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentProfile: {
    username: string;
    avatar?: string;
    country?: string;
    bio?: string;
  };
  onSuccess?: () => void;
}

const COUNTRIES = [
  { code: 'ru', name: 'Россия', flag: '🇷🇺' },
  { code: 'us', name: 'США', flag: '🇺🇸' },
  { code: 'gb', name: 'Великобритания', flag: '🇬🇧' },
  { code: 'de', name: 'Германия', flag: '🇩🇪' },
  { code: 'fr', name: 'Франция', flag: '🇫🇷' },
  { code: 'es', name: 'Испания', flag: '🇪🇸' },
  { code: 'it', name: 'Италия', flag: '🇮🇹' },
  { code: 'jp', name: 'Япония', flag: '🇯🇵' },
  { code: 'cn', name: 'Китай', flag: '🇨🇳' },
  { code: 'br', name: 'Бразилия', flag: '🇧🇷' },
];

export const EditProfileModal: React.FC<EditProfileModalProps> = ({
  isOpen,
  onClose,
  currentProfile,
  onSuccess,
}) => {
  const [username, setUsername] = useState(currentProfile.username);
  const [country, setCountry] = useState(currentProfile.country || '');
  const [bio, setBio] = useState(currentProfile.bio || '');
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | undefined>(
    currentProfile.avatar
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [updateProfile, { loading }] = useMutation(UPDATE_PROFILE, {
    onCompleted: (data) => {
      if (data.updateProfile) {
        onSuccess?.();
        onClose();
      }
    },
    onError: (error) => {
      console.error('Failed to update profile:', error);
      setErrors({ general: error.message });
    },
  });

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setErrors({ avatar: 'Размер файла не должен превышать 5 МБ' });
        return;
      }

      if (!file.type.startsWith('image/')) {
        setErrors({ avatar: 'Только изображения' });
        return;
      }

      setAvatarFile(file);
      setErrors({});
      
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRemoveAvatar = () => {
    setAvatarFile(null);
    setAvatarPreview(undefined);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    const newErrors: Record<string, string> = {};

    if (!username.trim()) {
      newErrors.username = 'Имя пользователя обязательно';
    } else if (username.length < 3) {
      newErrors.username = 'Минимум 3 символа';
    } else if (username.length > 20) {
      newErrors.username = 'Максимум 20 символов';
    }

    if (bio && bio.length > 500) {
      newErrors.bio = 'Максимум 500 символов';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    try {
      await updateProfile({
        variables: {
          input: {
            username: username.trim(),
            avatar: avatarFile || undefined,
            country: country || undefined,
            bio: bio.trim() || undefined,
          },
        },
      });
    } catch (error) {
      console.error('Update profile error:', error);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Редактировать профиль">
      <form className="edit-profile-modal" onSubmit={handleSubmit}>
        <div className="edit-profile-modal__avatar-section">
          <div className="edit-profile-modal__avatar-preview">
            {avatarPreview ? (
              <img src={avatarPreview} alt="Avatar preview" />
            ) : (
              <div className="edit-profile-modal__avatar-placeholder">
                {username[0]?.toUpperCase() || '?'}
              </div>
            )}
          </div>
          <div className="edit-profile-modal__avatar-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleAvatarChange}
              className="edit-profile-modal__avatar-input"
              aria-label="Загрузить аватар"
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              {avatarPreview ? 'Изменить' : 'Загрузить'}
            </Button>
            {avatarPreview && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleRemoveAvatar}
              >
                Удалить
              </Button>
            )}
          </div>
          {errors.avatar && (
            <p className="edit-profile-modal__error">{errors.avatar}</p>
          )}
          <p className="edit-profile-modal__hint">Максимальный размер: 5 МБ</p>
        </div>

        <div className="edit-profile-modal__field">
          <label htmlFor="username" className="edit-profile-modal__label">
            Имя пользователя *
          </label>
          <Input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Введите имя"
            error={errors.username}
          />
        </div>

        <div className="edit-profile-modal__field">
          <label htmlFor="country" className="edit-profile-modal__label">
            Страна
          </label>
          <select
            id="country"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="edit-profile-modal__select"
          >
            <option value="">Не выбрано</option>
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.flag} {c.name}
              </option>
            ))}
          </select>
        </div>

        <div className="edit-profile-modal__field">
          <label htmlFor="bio" className="edit-profile-modal__label">
            О себе
          </label>
          <textarea
            id="bio"
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            placeholder="Расскажите о себе..."
            rows={4}
            maxLength={500}
            className="edit-profile-modal__textarea"
          />
          <div className="edit-profile-modal__char-count">
            {bio.length} / 500
          </div>
          {errors.bio && (
            <p className="edit-profile-modal__error">{errors.bio}</p>
          )}
        </div>

        {errors.general && (
          <p className="edit-profile-modal__error edit-profile-modal__error--general">
            {errors.general}
          </p>
        )}

        <div className="edit-profile-modal__actions">
          <Button type="button" variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" variant="primary" loading={loading}>
            Сохранить
          </Button>
        </div>
      </form>
    </Modal>
  );
};