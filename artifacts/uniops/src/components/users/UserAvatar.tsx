import { clsx } from 'clsx';
import { initials } from '@/lib/formatters';

interface UserAvatarProps {
  name: string;
  avatar?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

const sizeMap = {
  xs: 'w-6 h-6 text-[10px]',
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-12 h-12 text-base',
  xl: 'w-16 h-16 text-lg',
};

const AVATAR_COLORS = [
  'hsl(220 90% 60% / 0.2)',
  'hsl(280 80% 60% / 0.2)',
  'hsl(160 70% 45% / 0.2)',
  'hsl(40 90% 55% / 0.2)',
  'hsl(0 70% 60% / 0.2)',
  'hsl(190 80% 50% / 0.2)',
];

const TEXT_COLORS = [
  'hsl(220 90% 70%)',
  'hsl(280 80% 70%)',
  'hsl(160 70% 55%)',
  'hsl(40 90% 65%)',
  'hsl(0 70% 70%)',
  'hsl(190 80% 60%)',
];

function getColorIndex(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return Math.abs(hash) % AVATAR_COLORS.length;
}

export function UserAvatar({ name, avatar, size = 'md', className }: UserAvatarProps) {
  const idx = getColorIndex(name);

  if (avatar) {
    return (
      <img
        src={avatar}
        alt={name}
        className={clsx('rounded-full object-cover flex-shrink-0', sizeMap[size], className)}
      />
    );
  }

  return (
    <div
      className={clsx('rounded-full flex items-center justify-center font-bold flex-shrink-0', sizeMap[size], className)}
      style={{ background: AVATAR_COLORS[idx], color: TEXT_COLORS[idx] }}
      title={name}
    >
      {initials(name)}
    </div>
  );
}
