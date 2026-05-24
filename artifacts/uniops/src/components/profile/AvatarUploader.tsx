import { useRef, useState } from 'react';
import { Camera, Upload, Trash2 } from 'lucide-react';
import { clsx } from 'clsx';
import { UserAvatar } from '@/components/users/UserAvatar';

interface AvatarUploaderProps {
  name: string;
  currentAvatar?: string;
  onUpload: (url: string) => void;
  size?: 'md' | 'lg';
}

export function AvatarUploader({ name, currentAvatar, onUpload, size = 'lg' }: AvatarUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | undefined>(currentAvatar);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const processFile = async (file: File) => {
    if (!file.type.startsWith('image/')) return;
    if (file.size > 5 * 1024 * 1024) return;

    setIsUploading(true);
    const reader = new FileReader();
    reader.onload = (e) => {
      const url = e.target?.result as string;
      setPreview(url);
      onUpload(url);
      setIsUploading(false);
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  };

  const avatarSize = size === 'lg' ? 'xl' : 'lg';
  const wrapperSize = size === 'lg' ? 'w-20 h-20' : 'w-14 h-14';

  return (
    <div className="flex items-center gap-4">
      <div
        className={clsx('relative group cursor-pointer', wrapperSize)}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <UserAvatar name={name} avatar={preview} size={avatarSize} className="w-full h-full" />
        <div className={clsx(
          'absolute inset-0 rounded-full flex items-center justify-center transition-all',
          isDragging ? 'bg-blue-500/40' : 'bg-black/50 opacity-0 group-hover:opacity-100'
        )}>
          {isUploading
            ? <div className="w-5 h-5 rounded-full border-2 border-white/20 border-t-white animate-spin" />
            : <Camera className="w-5 h-5 text-white" />}
        </div>
      </div>

      <div className="space-y-1.5">
        <button type="button" onClick={() => inputRef.current?.click()}
          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium transition-colors">
          <Upload className="w-3.5 h-3.5" /> Upload photo
        </button>
        {preview && (
          <button type="button" onClick={() => { setPreview(undefined); onUpload(''); }}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-red-400 transition-colors">
            <Trash2 className="w-3.5 h-3.5" /> Remove
          </button>
        )}
        <p className="text-xs text-muted-foreground/70">JPG, PNG or GIF · Max 5MB</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) processFile(f); }}
      />
    </div>
  );
}
