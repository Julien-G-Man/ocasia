'use client';

import AppSidebar from '@/components/sidebar/AppSidebar';
import AppHeader from '@/components/AppHeader';
import { cn } from '@/lib/utils';

interface AppLayoutProps {
  children: React.ReactNode;
  title: string;
  breadcrumb?: { label: string; href?: string }[];
  noSidebar?: boolean;
  mainClassName?: string;
}

const AppLayout = ({ children, title, breadcrumb, noSidebar = false, mainClassName }: AppLayoutProps) => {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {!noSidebar && <AppSidebar />}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <AppHeader title={title} breadcrumb={breadcrumb} />
        <main className={cn("flex-1 overflow-y-auto pb-20 md:pb-0", mainClassName)}>
          {children}
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
