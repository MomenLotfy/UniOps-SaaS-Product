import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useStore } from '@/store';
import { motion } from 'framer-motion';

interface LayoutProps {
  children: ReactNode;
}

export const Layout = ({ children }: LayoutProps) => {
  const { sidebarCollapsed } = useStore();

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <Header />
      <motion.main
        initial={false}
        animate={{
          marginLeft: sidebarCollapsed ? 72 : 240,
          paddingTop: 56,
        }}
        transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
        className="min-h-screen p-6"
      >
        {children}
      </motion.main>
    </div>
  );
};
