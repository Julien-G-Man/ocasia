'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Image from 'next/image';
import {
  Sparkles,
  LayoutDashboard,
  Bot,
  Brain,
  Layers,
  FolderOpen,
  Settings,
  LogOut,
  ChevronRight,
  Home,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/ai-tutor', icon: Bot, label: 'AI Tutor' },
  { href: '/quiz/create', icon: Brain, label: 'Quiz' },
  { href: '/flashcards', icon: Layers, label: 'Flashcards' },
  { href: '/materials', icon: FolderOpen, label: 'Materials' },
];

const AppSidebar = () => {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    router.push('/');
  };

  const isActive = (href: string) => {
    if (href === '/quiz/create') return pathname.startsWith('/quiz');
    if (href === '/flashcards') return pathname.startsWith('/flashcards');
    return pathname === href || pathname.startsWith(href + '/');
  };

  return (
    <>
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex flex-col w-60 shrink-0 min-h-screen border-r border-border bg-sidebar">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 h-16 border-b border-border shrink-0">
          <div className="w-7 h-7 rounded-lg overflow-hidden shrink-0">
            <Image src="/lamla_logo.png" alt="Lamla AI" width={28} height={28} className="w-full h-full object-cover" />
          </div>
          <span className="font-bold text-lg gradient-text">Lamla.ai</span>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 px-3 py-4 flex-1">
          <Link
            href="/"
            className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all duration-150 text-muted-foreground hover:text-foreground hover:bg-surface-hover border-l-2 border-transparent pl-[10px]"
          >
            <Home size={16} className="shrink-0" />
            Home
          </Link>
          <div className="my-1 border-t border-border/50" />
          {navItems.map(({ href, icon: Icon, label }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-all duration-150 group',
                  active
                    ? 'bg-primary/10 text-primary border-l-2 border-primary pl-[10px]'
                    : 'text-muted-foreground hover:text-foreground hover:bg-surface-hover border-l-2 border-transparent pl-[10px]'
                )}
              >
                <Icon size={16} className="shrink-0" />
                {label}
                {active && <ChevronRight size={14} className="ml-auto opacity-60" />}
              </Link>
            );
          })}
        </nav>

        {/* User section */}
        <div className="border-t border-border p-3">
          <Link
            href="/profile"
            className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-surface-hover transition-colors group"
          >
            {user?.profile_image ? (
              <Image
                src={user.profile_image}
                alt="avatar"
                width={32}
                height={32}
                className="rounded-full object-cover ring-2 ring-border group-hover:ring-primary transition-all"
              />
            ) : (
              <div className="w-8 h-8 rounded-full gradient-bg flex items-center justify-center text-sm font-bold text-white shrink-0">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">{user?.username || 'User'}</p>
              <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
            </div>
            <Settings size={14} className="text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
          </Link>
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2 w-full rounded-md text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors mt-1"
          >
            <LogOut size={16} className="shrink-0" />
            Logout
          </button>
        </div>
      </aside>

      {/* Mobile Bottom Nav */}
      <nav className="fixed bottom-0 left-0 right-0 md:hidden z-30 bg-background/90 backdrop-blur-md border-t border-border flex">
        {navItems.slice(0, 5).map(({ href, icon: Icon, label }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex flex-col items-center justify-center flex-1 py-2 gap-0.5 text-xs transition-colors',
                active ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <Icon size={18} />
              <span className="text-[10px]">{label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
};

export default AppSidebar;
