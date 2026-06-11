/**
 * UNMATCHED Design System - Avatar Component
 *
 * Компонент аватара для персонажей
 */

import React from 'react';

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string;
  alt?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'hero' | 'villain' | 'default';
  fallback?: string;
}

export const Avatar: React.FC<AvatarProps> = ({
  src,
  alt = '',
  size = 'md',
  variant = 'default',
  fallback,
  className = '',
  ...props
}) => {
  const classes = [
    'avatar',
    `avatar-${size}`,
    variant !== 'default' && variant,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const [imageError, setImageError] = React.useState(false);

  const handleError = () => {
    setImageError(true);
  };

  const content = React.useMemo(() => {
    if (!src || imageError) {
      return (
        <span className="avatar-fallback">
          {fallback || alt?.charAt(0)?.toUpperCase() || '?'}
        </span>
      );
    }
    return (
      <img
        src={src}
        alt={alt}
        onError={handleError}
      />
    );
  }, [src, imageError, fallback, alt]);

  return (
    <div className={classes} {...props}>
      {content}
    </div>
  );
};

export default Avatar;
