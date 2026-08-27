import React, { useState } from 'react';
import { Card } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Table } from '../../../components/ui/table';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Search, Clock, Share2, Bookmark, History, Target, Activity, Layers } from 'lucide-react';
import apiClient from '@/services/api/client';

type SearchEntity = {
  id: string;
  type: string;
  summary?: string;
  risk?: number;
  priority?: string;
  assets?: number;
};

type SearchResponse = {
  results?: SearchEntity[];
  data?: SearchEntity[];
  total?: number;
};

const InvestigationsSection = () => {
  const [searchQuery, setSearchQuery]     = useState('');
  const [activeTab, setActiveTab]         = useState('search');
  const [results, setResults]             = useState<SearchEntity[]>([]);
  const [loading, setLoading]             = useState(false);
  const [selectedEntity, setSelectedEntity] = useState<SearchEntity | null>(null);
  const [error, setError]                 = useState<string | null>(null);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.post('/api/v1/investigation/search', {
        query: searchQuery,
        entity_types: ['vulnerability', 'threat', 'repository', 'asset', 'package'],
        limit: 50,
      });
      const body: SearchResponse = res.data ?? res;
      const list = body.results ?? body.data ?? (Array.isArray(body) ? body : []);
      setResults(list);
    } catch (e: any) {
      setError(e?.message ?? 'Search failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const priorityColor: Record<string, string> = {
    critical: 'text-red-400',
    high:     'text-orange-400',
    medium:   'text-yellow-400',
    low:      'text-green-400',
  };

  return (
    <div className="space-y-6">
      {/* Top Search Bar */}
      <Card className="p-4 flex items-center gap-4 bg-surface-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={18} />
          <Input
            className="pl-10"
            placeholder="Search findings, assets, repositories, packages, CVEs…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <Button onClick={handleSearch} disabled={loading || !searchQuery.trim()}>
          {loading ? 'Searching…' : 'Investigate'}
        </Button>
      </Card>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-white/10">
        {['search', 'timeline', 'correlation'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2 px-2 text-xs font-medium transition-colors ${
              activeTab === tab
                ? 'text-indigo-400 border-b-2 border-indigo-400'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Results Area */}
        <div className="lg:col-span-2 space-y-6">
          {activeTab === 'search' && (
            <Card className="p-6">
              <h3 className="text-sm uppercase text-muted-foreground mb-4">
                Investigation Results
                {results.length > 0 && (
                  <span className="ml-2 text-indigo-400 normal-case">
                    — {results.length} match{results.length !== 1 ? 'es' : ''}
                  </span>
                )}
              </h3>

              {error && (
                <p className="text-xs text-red-400 mb-4">Search error: {error}</p>
              )}

              <Table>
                <thead className="text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left">Entity</th>
                    <th className="text-left">Type</th>
                    <th className="text-right">Risk</th>
                    <th className="text-center">Priority</th>
                    <th className="text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {results.length > 0 ? results.map(res => (
                    <tr
                      key={res.id}
                      className="border-t border-white/5 hover:bg-white/5 transition-colors cursor-pointer"
                      onClick={() => setSelectedEntity(res)}
                    >
                      <td className="py-3">
                        <div className="flex flex-col">
                          <span className="font-medium text-sm">{res.id}</span>
                          {res.summary && (
                            <span className="text-xs text-muted-foreground truncate max-w-xs">
                              {res.summary}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3">
                        <Badge variant="outline" className="text-[10px] capitalize">
                          {res.type}
                        </Badge>
                      </td>
                      <td className="py-3 text-right font-mono text-sm">
                        {res.risk != null ? res.risk : '—'}
                      </td>
                      <td className="py-3 text-center">
                        {res.priority ? (
                          <span className={`text-xs capitalize ${priorityColor[res.priority] ?? 'text-muted-foreground'}`}>
                            {res.priority}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="py-3 text-center">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-indigo-400 h-7 px-2"
                          onClick={(e) => { e.stopPropagation(); setSelectedEntity(res); setActiveTab('timeline'); }}
                        >
                          Inspect
                        </Button>
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-muted-foreground text-sm">
                        {loading
                          ? 'Searching intelligence base…'
                          : searchQuery
                          ? 'No entities found. Try a broader search term.'
                          : 'Enter a query above to search across findings, repositories, assets, and packages.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </Table>
            </Card>
          )}

          {activeTab === 'timeline' && (
            <Card className="p-6">
              <h3 className="text-sm uppercase text-muted-foreground mb-4">Entity Timeline</h3>
              {!selectedEntity ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Clock size={40} className="mb-4 opacity-20" />
                  <span className="text-sm">Select an entity from search results to view its historical timeline.</span>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground mb-4">
                    Showing activity for <span className="text-foreground font-medium">{selectedEntity.id}</span>
                    {' '}({selectedEntity.type})
                  </p>
                  <div className="space-y-4 relative before:absolute before:left-4 before:top-0 before:bottom-0 before:w-px before:bg-white/10">
                    <div className="relative pl-10">
                      <div className="absolute left-3 top-1 w-2 h-2 bg-indigo-500 rounded-full ring-4 ring-indigo-500/20" />
                      <div className="p-3 bg-surface-2 rounded-lg border border-white/5">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-xs font-bold text-foreground">First Detected</span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          Entity <span className="text-foreground">{selectedEntity.id}</span> entered the
                          intelligence graph with priority <span className="capitalize">{selectedEntity.priority ?? 'unknown'}</span>.
                        </span>
                      </div>
                    </div>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-4">
                    Full timeline requires a backend integration with scan history. Connect a scan to see all events.
                  </p>
                </div>
              )}
            </Card>
          )}

          {activeTab === 'correlation' && (
            <Card className="p-6">
              <h3 className="text-sm uppercase text-muted-foreground mb-4">Correlation Analysis</h3>
              {!selectedEntity ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Share2 size={40} className="mb-4 opacity-20" />
                  <span className="text-sm">Select an entity from search to uncover related nodes.</span>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground mb-4">
                    Related entities for <span className="text-foreground font-medium">{selectedEntity.id}</span>
                  </p>
                  <div className="p-6 rounded-lg border border-white/10 text-center">
                    <Layers size={32} className="mx-auto mb-3 text-indigo-400 opacity-50" />
                    <p className="text-sm text-muted-foreground">
                      Graph correlation requires entities to be connected via scan findings. Run a scan to build the knowledge graph.
                    </p>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="text-sm uppercase text-muted-foreground mb-4 flex items-center gap-2">
              <Target size={16} /> Selected Entity
            </h3>
            {!selectedEntity ? (
              <span className="text-xs text-muted-foreground italic">
                No entity selected. Run a search and click a row.
              </span>
            ) : (
              <div className="space-y-4">
                <div className="flex flex-col">
                  <span className="text-[10px] text-muted-foreground uppercase">Entity ID</span>
                  <span className="text-sm font-medium break-all">{selectedEntity.id}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-muted-foreground uppercase">Type</span>
                  <Badge variant="outline" className="text-[10px] w-fit capitalize">
                    {selectedEntity.type}
                  </Badge>
                </div>
                {selectedEntity.risk != null && (
                  <div className="flex flex-col">
                    <span className="text-[10px] text-muted-foreground uppercase">Risk Score</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold">{selectedEntity.risk}</span>
                      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${selectedEntity.priority === 'critical' ? 'bg-red-500' : 'bg-orange-500'}`}
                          style={{ width: `${Math.min(100, (selectedEntity.risk ?? 0) * 10)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                )}
                {selectedEntity.summary && (
                  <div className="flex flex-col">
                    <span className="text-[10px] text-muted-foreground uppercase">Summary</span>
                    <span className="text-xs text-muted-foreground">{selectedEntity.summary}</span>
                  </div>
                )}
                <div className="pt-4 border-t border-white/5">
                  <Button className="w-full text-xs h-8" variant="outline" onClick={() => setActiveTab('timeline')}>
                    <Clock size={14} className="mr-2" /> View Timeline
                  </Button>
                </div>
              </div>
            )}
          </Card>

          <Card className="p-6">
            <h3 className="text-sm uppercase text-muted-foreground mb-4 flex items-center gap-2">
              <Activity size={16} /> Session
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Results Loaded</span>
                <span className="font-mono tabular-nums">{results.length}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Active Entity</span>
                <span className="font-mono truncate max-w-[100px]">
                  {selectedEntity?.id ?? '—'}
                </span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Current Tab</span>
                <Badge variant="outline" className="text-[9px] capitalize">{activeTab}</Badge>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default InvestigationsSection;
