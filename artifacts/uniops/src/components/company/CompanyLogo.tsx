import { useRef, useState } from 'react';
import { Building2, Upload, Camera, Trash2 } from 'lucide-react';
import { clsx } from 'clsx';

interface CompanyLogoProps {
  name: string;
  logoUrl?: string;
  onUpload?: (url: string) => void;
  editable?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const sizeMap = { sm: 'w-10 h-10 text-sm', md: 'w-14 h-14 text-lg', lg: 'w-20 h-20 text-2xl' };
const iconSize = { sm: 'w-5 h-5', md: 'w-7 h-7', lg: 'w-10 h-10' };

export function CompanyLogo({ name, logoUrl, onUpload, editable = false, size = 'md' }: CompanyLogoProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState(logoUrl);
  const [isDragging, setIsDragging] = useState(false);

  const processFile = (file: File) => {
    if (!file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const url = e.target?.result as string;
      setPreview(url);
      onUpload?.(url);
    };
    reader.readAsDataURL(file);
  };

  const initials = name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();

  return (
    <div className="flex items-center gap-4">
      <div
        className={clsx('relative group rounded-2xl flex items-center justify-center font-bold flex-shrink-0 overflow-hidden border-2 transition-all',
          sizeMap[size],
          editable && 'cursor-pointer',
          isDragging ? 'border-blue-500 scale-105' : 'border-border/30')}
        style={{ background: preview ? undefined : 'hsl(220 90% 60% / 0.15)', color: 'hsl(220 90% 70%)' }}
        onDragOver={editable ? (e) => { e.preventDefault(); setIsDragging(true); } : undefined}
        onDragLeave={editable ? () => setIsDragging(false) : undefined}
        onDrop={editable ? (e) => { e.preventDefault(); setIsDragging(false); const f = e.dataTransfer.files[0]; if (f) processFile(f); } : undefined}
        onClick={editable ? () => inputRef.current?.click() : undefined}
      >
        {preview
          ? <img src={preview} alt={name} className="w-full h-full object-cover" />
          : preview === undefined && logoUrl === undefined
            ? <Building2 className={iconSize[size]} />
            : <span>{initials}</span>}

        {editable && (
          <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <Camera className="w-5 h-5 text-white" />
          </div>
        )}
      </div>

      {editable && (
        <div className="space-y-1.5">
          <button type="button" onClick={() => inputRef.current?.click()}
            className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium transition-colors">
            <Upload className="w-3.5 h-3.5" /> Upload logo
          </button>
          {preview && (
            <button type="button" onClick={() => { setPreview(undefined); onUpload?.(''); }}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-red-400 transition-colors">
              <Trash2 className="w-3.5 h-3.5" /> Remove
            </button>
          )}
          <p className="text-xs text-muted-foreground/70">PNG or SVG · Max 2MB · Square recommended</p>
        </div>
      )}

      <input ref={inputRef} type="file" accept="image/*" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) processFile(f); }} />
    </div>
  );
}
