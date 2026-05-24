import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import { AuthProvider } from '@/contexts/AuthContext';
import { CompanyProvider } from '@/contexts/CompanyContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { IntegrationsProvider } from '@/contexts/IntegrationsContext';
import { WebSocketProvider } from '@/contexts/WebSocketContext';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:                   30_000,
      refetchOnWindowFocus:        true,
      refetchIntervalInBackground: false,
      retry:                       2,
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <CompanyProvider>
              <WebSocketProvider>
                <IntegrationsProvider>
                  <NotificationProvider>
                    <App />
                  </NotificationProvider>
                </IntegrationsProvider>
              </WebSocketProvider>
            </CompanyProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
