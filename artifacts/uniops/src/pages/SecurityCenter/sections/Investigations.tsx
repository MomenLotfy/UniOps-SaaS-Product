import React, { useEffect, useState } from 'react';
import { Card, Title, Text, Badge, Table, Button, Input, Select } from '../../components/ui';
import { Search, Filter, Clock, Share2, Bookmark, History, Target, Activity, Layers } from 'lucide-react';

const InvestigationsSection = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('search');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);

  const mockResults = [
    { id: 'CVE-2024-1234', type: 'CVE', summary: 'Critical Remote Code Execution', risk: 9.8, assets: 45, priority: 'critical' },
    { id: 'Repo-Auth-Service', type: 'Repository', summary: 'Authentication Microservice', risk: 4.2, assets: 12, priority: 'medium' },
    { id: 'Prod-Cluster-01', type: 'Cluster', summary: 'Production US-East-1', risk: 6.5, assets: 150, priority: 'high' },
    { id: 'Package-Libxml2', type: 'Package', summary: 'XML Parsing Library', risk: 7.1, assets: 200, priority: 'high' },
  ];

  const handleSearch = async () => {
    setLoading(true);
    // Simulate API call to /security/search
    setTimeout(() => {
      setResults(mockResults.filter(r =>
        r.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.summary.toLowerCase().includes(searchQuery.toLowerCase())
      ));
      setLoading(false);
    }, 600);
  };

  return (
    <div className="space-y-6">
      {/* Top Search Bar */}
      <Card className="p-4 flex items-center gap-4 bg-surface-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={18} />
          <Input
            className="pl-10"
            placeholder="Search findings, assets, repositories, or packages..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <Button onClick={handleSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Investigate'}
        </Button>
        <div className="flex items-center gap-2 ml-auto">
          <Button variant="ghost" size="sm"><Bookmark size={16} className="mr-2" /> Bookmarks</Button>
          <Button variant="ghost" size="sm"><History size={16} className="mr-2" /> History</Button>
        </div>
      </Card>

      {/* Investigation Tabs */}
      <div className="flex gap-4 border-b border-white/10">
        {['search', 'timeline', 'correlation', 'risk'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2 px-2 text-xs font-medium transition-colors ${
              activeTab === tab ? 'text-indigo-400 border-b-2 border-indigo-400' : 'text-muted-foreground hover:text-foreground'
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
              <Title className="mb-4 text-sm uppercase text-muted-foreground">Investigation Results</Title>
              <Table>
                <thead className="text-xs text-muted-foreground uppercase">
                  <tr>
                    <th className="text-left">Entity</th>
                    <th className="text-left">Type</th>
                    <th className="text-right">Risk Score</th>
                    <th className="text-right">Impact</th>
                    <th className="text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {results.length > 0 ? results.map(res => (
                    <tr key={res.id} className="border-t border-white/5 hover:bg-white/5 transition-colors cursor-pointer" onClick={() => setSelectedEntity(res)}>
                      <td className="py-3">
                        <div className="flex flex-col">
                          <span className="font-medium text-sm">{res.id}</span>
                          <span className="text-xs text-muted-foreground">{res.summary}</span>
                        </div>
                      </td>
                      <td className="py-3">
                        <Badge variant="outline" className="text-[10px]">{res.type}</Badge>
                      </td>
                      <td className="py-3 text-right font-mono text-sm">{res.risk}</td>
                      <td className="py-3 text-right text-xs text-muted-foreground">{res.assets} assets</td>
                      <td className="py-3 text-center">
                        <Button size="sm" variant="ghost" className="text-indigo-400 h-7 px-2">Inspect</Button>
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-muted-foreground text-sm">
                        {loading ? 'Searching intelligence base...' : 'No entities found. Try a different query.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </Table>
            </Card>
          )}

          {activeTab === 'timeline' && (
            <Card className="p-6">
              <Title className="mb-4 text-sm uppercase text-muted-foreground">Entity Timeline</Title>
              {!selectedEntity ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Clock size={40} className="mb-4 opacity-20" />
                  <Text className="text-sm">Select an entity from search results to view its historical timeline.</Text>
                </div>
              ) : (
                <div className="space-y-6 relative before:absolute before:left-4 before:top-0 before:bottom-0 before:w-px before:bg-white/10">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="relative pl-10">
                      <div className="absolute left-3 top-1 w-2 h-2 bg-indigo-500 rounded-full ring-4 ring-indigo-500/20" />
                      <div className="p-3 bg-surface-2 rounded-lg border border-white/5">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-bold text-foreground">Security Event {i}</span>
                          <span className="text-[10px] text-muted-foreground">2026-06-{(26-i).toString().padStart(2, '0')} 14:20</span>
                        </div>
                        <Text className="text-xs text-muted-foreground">
                          Deterministic event detected for {selectedEntity.id}. State changed from 'Low' to 'Critical' risk.
                        </Text>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {activeTab === 'correlation' && (
            <Card className="p-6">
              <Title className="mb-4 text-sm uppercase text-muted-foreground">Correlation Analysis</Title>
              {!selectedEntity ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Share2 size={40} className="mb-4 opacity-20" />
                  <Text className="text-sm">Select an entity to uncover deterministic correlations across the graph.</Text>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { type: 'Package', id: 'libxml2', rel: 'DEPENDENCY', depth: 1 },
                    { type: 'Repository', id: 'auth-service', rel: 'CONTAINS', depth: 2 },
                    { type: 'Asset', id: 'prod-pod-01', rel: 'RUNS_ON', depth: 3 },
                    { type: 'Team', id: 'Platform-Sec', rel: 'OWNED_BY', depth: 4 },
                  ].map((corr, idx) => (
                    <div key={idx} className="p-4 bg-surface-2 rounded-lg border border-white/5 flex items-center gap-4">
                      <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                        <Layers size={16} />
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between items-center">
                          <span className="text-xs font-medium">{corr.id}</span>
                          <Badge variant="outline" className="text-[9px]">{corr.type}</Badge>
                        </div>
                        <Text className="text-[10px] text-muted-foreground">
                          Linked via <span className="text-foreground font-semibold">{corr.rel}</span> (Depth: {corr.depth})
                        </Text>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {activeTab === 'risk' && (
            <Card className="p-6">
              <Title className="mb-4 text-sm uppercase text-muted-foreground">Risk Intelligence Summary</Title>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                  <Text className="text-[10px] text-red-400 uppercase font-bold">Critical Impact</Text>
                  <Title className="text-2xl font-bold">84%</Title>
                </div>
                <div className="p-4 bg-orange-500/10 border border-orange-500/20 rounded-lg">
                  <Text className="text-[10px] text-orange-400 uppercase font-bold">Blast Radius</Text>
                  <Title className="text-2xl font-bold">High</Title>
                </div>
                <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                  <Text className="text-[10px] text-blue-400 uppercase font-bold">Confidence</Text>
                  <Title className="text-2xl font-bold">Deterministic</Title>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Right Sidebar: Investigation Context */}
        <div className="space-y-6">
          <Card className="p-6">
            <Title className="mb-4 text-sm uppercase text-muted-foreground flex items-center gap-2">
              <Target size={16} /> Target Context
            </Title>
            {!selectedEntity ? (
              <Text className="text-xs text-muted-foreground italic">No entity selected for deep investigation.</Text>
            ) : (
              <div className="space-y-4">
                <div>
                  <Text className="text-[10px] text-muted-foreground uppercase">Entity ID</Text>
                  <Text className="text-sm font-medium">{selectedEntity.id}</Text>
                </div>
                <div>
                  <Text className="text-[10px] text-muted-foreground uppercase">Type</Text>
                  <Badge variant="outline" className="text-[10px]">{selectedEntity.type}</Badge>
                </div>
                <div>
                  <Text className="text-[10px] text-muted-foreground uppercase">Risk Score</Text>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold">{selectedEntity.risk}</span>
                    <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${selectedEntity.priority === 'critical' ? 'bg-red-500' : 'bg-orange-500'}`}
                        style={{ width: `${selectedEntity.risk * 10}%` }}
                      />
                    </div>
                  </div>
                </div>
                <div className="pt-4 border-t border-white/5">
                  <Button className="w-full text-xs h-8" variant="outline">
                    <Bookmark size={14} className="mr-2" /> Bookmark Entity
                  </Button>
                </div>
              </div>
            )}
          </Card>

          <Card className="p-6">
            <Title className="mb-4 text-sm uppercase text-muted-foreground flex items-center gap-2">
              <Activity size={16} /> Investigation State
            </Title>
            <div className="space-y-3">
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Session</span>
                <span className="font-mono text-indigo-400">SESS-923-AX</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Filters Active</span>
                <Badge variant="outline" className="text-[9px]">3</Badge>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Bookmarks</span>
                <Badge variant="outline" className="text-[9px]">12</Badge>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Query Time</span>
                <span className="font-mono">14ms</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
        <Text className="text-[10px] text-indigo-300 leading-relaxed">
          The Security Investigation Engine provides deterministic reasoning over the Intelligence Platform.
          It allows security researchers to pivot from a finding to an asset, correlate its blast radius,
          and reconstruct its historical timeline without any probabilistic AI interference.
        </Text>
      </div>
    </div>
  );
};

export default InvestigationsSection;
