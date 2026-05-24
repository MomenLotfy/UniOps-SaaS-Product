import { useApi } from '@/hooks/use-api';
import { Download } from 'lucide-react';
import { formatCurrency, formatDate } from '@/lib/formatters';

export function BillingHistory() {
  const { data, loading } = useApi<any>('/billing/invoices?page_size=10');
  const invoices = data?.data ?? data ?? [];

  if (loading) return <p className="text-sm text-muted-foreground">Loading billing history...</p>;
  if (invoices.length === 0) return <p className="text-sm text-muted-foreground">No invoices yet.</p>;

  return (
    <div className="space-y-2">
      {invoices.map((inv: any) => (
        <div key={inv.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
          <div>
            <div className="text-sm font-medium text-foreground">{inv.number ?? inv.description ?? 'Invoice'}</div>
            <div className="text-xs text-muted-foreground">{inv.period ?? (inv.created_at ? formatDate(inv.created_at) : '')}</div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-foreground">{formatCurrency((inv.amount ?? 0) / 100)}</span>
            <span className={`text-xs font-medium ${inv.status === 'paid' ? 'text-green-400' : 'text-yellow-400'}`}>{inv.status}</span>
            {inv.pdf_url && (
              <a href={inv.pdf_url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground">
                <Download className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
