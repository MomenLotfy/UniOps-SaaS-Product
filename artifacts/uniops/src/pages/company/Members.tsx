// artifacts/uniops/src/pages/company/Members.tsx
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Users, UserPlus, Mail, Shield, Trash2, Search } from 'lucide-react';
import { usersApi } from '@/services/api/users';
import type { User } from '@/types/user';
import { ROLE_LABELS, ROLE_COLORS } from '@/lib/constants';
import { initials, formatRelative } from '@/lib/formatters';
import { useDebounce } from '@/hooks/use-debounce';
import { clsx } from 'clsx';

export default function Members() {
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search);

  useEffect(() => {
    setIsLoading(true);
    setError('');
    usersApi.list({ search: debouncedSearch })
      .then((r) => {
        const list = Array.isArray(r) ? r : (r as any)?.data ?? [];
        setUsers(list);
      })
      .catch((err) => setError(err.message ?? 'Failed to load members'))
      .finally(() => setIsLoading(false));
  }, [debouncedSearch]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-8 h-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
        <span className="ml-3 text-gray-400">جاري تحميل الأعضاء...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <p className="text-red-400 text-lg font-medium">⚠️ {error}</p>
        <button onClick={() => setSearch('')} className="action-btn">إعادة المحاولة</button>
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Company Members</h1>
          <p className="page-subtitle">{users.length} members · Professional Plan (25 max)</p>
        </div>
        <button className="action-btn-primary"><UserPlus className="w-4 h-4" />Invite member</button>
      </div>

      <div className="card-base">
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search members..."
            className="w-full pl-9 pr-4 py-2 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500/50"
            style={{ background: 'hsl(230 18% 9%)', borderColor: 'hsl(230 15% 14%)', color: 'white' }} />
        </div>

        {users.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <Users className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No members found{debouncedSearch ? ' matching your search' : ''}.</p>
            {debouncedSearch && <button onClick={() => setSearch('')} className="text-blue-400 text-sm mt-2 hover:underline">Clear search</button>}
          </div>
        ) : (
          <div className="space-y-2">
            {users.map((user) => (
              <div key={user.id} className="flex items-center gap-3 p-3 rounded-lg border border-border/50" style={{ background: 'hsl(230 18% 9%)' }}>
                <div className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
                  style={{ background: 'hsl(220 90% 60% / 0.2)', color: 'hsl(220 90% 70%)' }}>
                  {initials(user?.displayName || 'U')}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground">{user?.displayName || 'Unknown User'}</div>
                  <div className="text-xs text-muted-foreground">{user?.email || ''}</div>
                </div>
                <span className={clsx('text-xs font-medium', ROLE_COLORS[user?.role] || 'text-gray-400')}>
                  {ROLE_LABELS[user?.role] || user?.role}
                </span>
                <span className="text-xs text-muted-foreground hidden xl:block">
                  {user?.lastLogin ? `Active ${formatRelative(user.lastLogin)}` : 'Never logged in'}
                </span>
                <div className="flex items-center gap-1">
                  <button className="p-1.5 rounded text-muted-foreground hover:text-foreground"><Shield className="w-3.5 h-3.5" /></button>
                  <button className="p-1.5 rounded text-muted-foreground hover:text-foreground"><Mail className="w-3.5 h-3.5" /></button>
                  <button className="p-1.5 rounded text-muted-foreground hover:text-red-400"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
