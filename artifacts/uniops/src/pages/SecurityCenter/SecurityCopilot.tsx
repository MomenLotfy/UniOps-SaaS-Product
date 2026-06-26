import { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  Search,
  User,
  Bot,
  ChevronRight,
  Plus,
  Trash2,
  Clock,
  Shield,
  AlertCircle,
  Lock,
  Package,
  Layout,
  ArrowRight
} from 'lucide-react';
import { clsx } from 'clsx';
import { policiesApi, exceptionsApi } from '../../services/api/security';
import apiClient from '../../services/api/client';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

interface CopilotContext {
  repoId: string | null;
  findingId: string | null;
  scanId: string | null;
}

export default function SecurityCopilot() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConvId, setCurrentConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [context, setContext] = useState<CopilotContext>({
    repoId: null, findingId: null, scanId: null
  });

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    if (currentConvId) loadMessages(currentConvId);
  }, [currentConvId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function loadConversations() {
    try {
      const res = await apiClient.get('/api/v1/copilot/conversations');
      setConversations(res.data.data || []);
    } catch (e) {
      console.error('Failed to load conversations', e);
    }
  }

  async function loadMessages(convId: string) {
    try {
      const res = await apiClient.get(`/api/v1/copilot/conversations/${convId}/messages`);
      setMessages(res.data.data || []);
    } catch (e) {
      console.error('Failed to load messages', e);
    }
  }

  async function startNewChat() {
    try {
      const res = await apiClient.post('/api/v1/copilot/conversations', {
        title: 'New Security Investigation',
        metadata: { timestamp: new Date().toISOString() }
      });
      const newConv = res.data.data;
      setCurrentConvId(newConv.id);
      setMessages([]);
      await loadConversations();
    } catch (e) {
      console.error('Failed to start new chat', e);
    }
  }

  async function sendMessage() {
    if (!inputValue.trim() || !currentConvId) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await apiClient.post('/api/v1/copilot/chat', {
        conversation_id: currentConvId,
        message: inputValue,
        repo_id: context.repoId,
        finding_id: context.findingId,
        scan_id: context.scanId
      });

      const aiMsg: Message = {
        id: (res.data.data.message_id || Date.now().toString()),
        role: 'assistant',
        content: res.data.data.message,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (e) {
      console.error('Chat error', e);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-background">
      {/* Left Sidebar: Conversations */}
      <div className="w-72 border-r border-border flex flex-col bg-background/50">
        <div className="p-4 border-b border-border">
          <button
            onClick={startNewChat}
            className="w-full py-2 px-4 rounded-lg bg-primary text-white text-xs font-medium flex items-center justify-center gap-2 hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-3 h-3" /> New Investigation
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider px-3 py-2">
            Recent Investigations
          </div>
          {conversations.map(conv => (
            <div
              key={conv.id}
              onClick={() => setCurrentConvId(conv.id)}
              className={clsx(
                'group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all text-xs',
                currentConvId === conv.id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
              )}
            >
              <MessageSquare className="w-3 h-3" />
              <span className="flex-1 truncate">{conv.title}</span>
              <Trash2
                className="w-3 h-3 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity"
                onClick={(e) => { e.stopPropagation(); /* delete call here */ }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Center: Chat Conversation */}
      <div className="flex-1 flex flex-col relative bg-background">
        {!currentConvId ? (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center text-primary mb-4">
              <Bot className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold">Security Copilot</h2>
            <p className="text-sm text-muted-foreground max-w-md">
              Analyze your security posture, investigate vulnerabilities, and generate remediation plans with AI.
            </p>
            <div className="grid grid-cols-2 gap-3 mt-6 w-full max-w-lg">
              {[
                "Explain this finding",
                "Why is this critical?",
                "Show remediation steps",
                "Summarize this scan"
              ].map(suggestion => (
                <button
                  key={suggestion}
                  onClick={() => {
                    setCurrentConvId(conversations[0]?.id || null); // Simple logic for new chat
                    setInputValue(suggestion);
                  }}
                  className="p-3 text-left text-xs rounded-xl border border-border bg-muted/30 hover:border-primary/50 hover:bg-primary/5 transition-all"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-6 space-y-6" ref={scrollRef}>
              {messages.map((msg, i) => (
                <div key={i} className={clsx('flex gap-4', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center text-primary shrink-0">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}
                  <div className={clsx(
                    'max-w-[80%] rounded-2xl p-4 text-sm',
                    msg.role === 'user' ? 'bg-primary text-white rounded-tr-none' : 'bg-muted/50 text-foreground rounded-tl-none border border-border'
                  )}>
                    <div className="whitespace-pre-wrap leading-relaxed">
                      {msg.content}
                    </div>
                    <div className="mt-2 text-[10px] opacity-50 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-lg bg-foreground/10 flex items-center justify-center text-foreground shrink-0">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-4 justify-start">
                  <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center text-primary shrink-0">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div className="bg-muted/50 rounded-2xl p-4 rounded-tl-none border border-border flex gap-1 items-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              )}
            </div>
            <div className="p-6 border-t border-border bg-background/80 backdrop-blur-md">
              <div className="max-w-4xl mx-auto relative">
                <input
                  className="w-full pr-12 pl-4 py-3 rounded-xl border border-border bg-muted/30 text-sm focus:outline-none focus:border-primary/50 transition-all"
                  placeholder="Ask Copilot about your security posture..."
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && sendMessage()}
                />
                <button
                  onClick={sendMessage}
                  disabled={isLoading || !inputValue.trim()}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-all"
                >
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Right Sidebar: Context Panel */}
      <div className="w-80 border-l border-border flex flex-col bg-background/50">
        <div className="p-4 border-b border-border">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Current Context</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          <ContextSection
            title="Repository"
            icon={Layout}
            value={context.repoId}
            placeholder="No repository selected"
            onChange={(id) => setContext(p => ({ ...p, repoId: id }))}
          />
          <ContextSection
            title="Scan"
            icon={Clock}
            value={context.scanId}
            placeholder="No scan selected"
            onChange={(id) => setContext(p => ({ ...p, scanId: id }))}
          />
          <ContextSection
            title="Finding"
            icon={AlertCircle}
            value={context.findingId}
            placeholder="No finding selected"
            onChange={(id) => setContext(p => ({ ...p, findingId: id }))}
          />
          <div className="pt-4 space-y-3">
            <div className="text-[10px] font-medium text-muted-foreground uppercase px-1">Quick Insight</div>
            <div className="p-3 rounded-xl bg-muted/30 border border-border space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Overall Score</span>
                <span className="font-bold text-primary">84/100</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Critical Risks</span>
                <span className="font-bold text-red-400">12</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Compliance</span>
                <span className="font-bold text-green-400">SOC2 Pass</span>
              </div>
            </div>
          </div>
        </div>
      </div
    </div>
  );
}

function ContextSection({ title, icon: Icon, value, placeholder, onChange }: any) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <Icon className="w-3 h-3" /> {title}
      </div>
      <div className="p-2 rounded-lg border border-border bg-background text-xs flex items-center justify-between group">
        <span className={clsx('truncate', !value && 'text-muted-foreground italic')}>
          {value || placeholder}
        </span>
        {value && (
          <button
            onClick={() => onChange(null)}
            className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-red-400 transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </div>
    </div>
  );
}
