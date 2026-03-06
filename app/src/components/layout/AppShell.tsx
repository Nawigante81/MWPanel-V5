import { useEffect, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { dashboardApi, notificationsApi, profileApi } from '@/lib/api';
import mwLogo from '@/assets/mw-logo.svg';
import {
  LayoutDashboard,
  Home,
  Users,
  CheckSquare,
  Settings,
  Menu,
  LogOut,
  Bell,
  ChevronDown,
  Sun,
  Moon,
  User,
  BarChart3,
  Calendar as CalendarIcon,
  FileText,
  Calculator,
  Target,
  ClipboardList,
  Share2,
} from 'lucide-react';

interface NavItem {
  label: string;
  path: string;
  icon: React.ElementType;
  badge?: number;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard },
  { label: 'Oferty', path: '/listings', icon: Home, badge: 0 },
  { label: 'Kontakty', path: '/contacts', icon: Users },
  { label: 'Leady', path: '/leads', icon: Target },
  { label: 'Zadania', path: '/tasks', icon: CheckSquare },
  { label: 'Publikacje', path: '/publications', icon: Share2 },
  { label: 'Audit log', path: '/audit-logs', icon: ClipboardList },
  { label: 'Kalendarz', path: '/calendar', icon: CalendarIcon },
  { label: 'Dokumenty', path: '/documents', icon: FileText },
  { label: 'Prowizje', path: '/commission', icon: Calculator },
  { label: 'Raporty', path: '/reports', icon: BarChart3 },
  { label: 'Ustawienia', path: '/settings', icon: Settings },
];

function Sidebar({ className, onNavigate }: { className?: string; onNavigate?: () => void }) {
  const location = useLocation();

  const { data: dashboardData } = useQuery({
    queryKey: ['sidebar-stats'],
    queryFn: dashboardApi.getDashboard,
    refetchInterval: 30000,
  });

  const activeOffers = Number(dashboardData?.offers_active || 0);
  const newToday = Number(dashboardData?.offers_new_today || 0);
  const taskBadge = Number(dashboardData?.tasks_actionable ?? 0);

  return (
    <div 
      className={cn(
        'flex h-full flex-col bg-gradient-to-b from-sidebar to-sidebar/95 backdrop-blur-xl',
        'border-r border-sidebar-border/50',
        className
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center px-6">
        <Link to="/" className="flex items-center group">
          <img src={mwLogo} alt="MWPanel" className="h-9 w-auto object-contain" />
        </Link>
      </div>

      <Separator className="bg-sidebar-border/50 mx-4 w-auto" />

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4 overflow-y-auto">
        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 py-2">
          Menu
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path || 
            (item.path !== '/' && location.pathname.startsWith(item.path));
          const badge = item.path === '/tasks' ? taskBadge : item.badge;

          return (
            <Link
              key={item.path}
              to={item.path}
              onClick={onNavigate}
              className={cn(
                'flex items-center justify-between rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
                'hover:translate-x-0.5',
                isActive
                  ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground'
              )}
            >
              <div className="flex items-center gap-3">
                <Icon className={cn(
                  'h-5 w-5 transition-transform duration-200',
                  isActive && 'scale-110'
                )} />
                {item.label}
              </div>
              {badge && badge > 0 ? (
                <Badge 
                  variant={isActive ? 'secondary' : 'default'} 
                  className="h-5 min-w-5 px-1.5 text-[10px]"
                >
                  {badge}
                </Badge>
              ) : null}
            </Link>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className="p-4 space-y-3">
        <Separator className="bg-sidebar-border/50" />
        
        {/* Quick stats */}
        <div className="rounded-xl bg-sidebar-accent/50 p-3 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Aktywne oferty</span>
            <span className="font-semibold text-primary">{activeOffers}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Nowe dzisiaj</span>
            <span className="font-semibold text-green-500">+{newToday}</span>
          </div>
        </div>

        <div className="text-[10px] text-muted-foreground text-center">
          MWPanel v1.0 • autor Tomaszkien
        </div>
      </div>
    </div>
  );
}

function Topbar() {
  const { user, logout } = useAuth();
  const { resolvedTheme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const { data: profileData } = useQuery({
    queryKey: ['profile', user?.id],
    queryFn: profileApi.get,
    enabled: !!user?.id,
    refetchInterval: 30000,
  });

  const { data: notifData, refetch: refetchNotifications } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list({ limit: 20, offset: 0 }),
    refetchInterval: 15000,
  });

  const unreadCount = Number(notifData?.unread_count || 0);
  const notifications = notifData?.items || [];

  const initials = (profileData?.name || user?.name || 'U')
    .split(' ')
    .map((n: string) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  const timeAgo = (iso?: string) => {
    if (!iso) return '';
    const diff = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
    if (diff < 60) return `${diff}s temu`;
    if (diff < 3600) return `${Math.floor(diff / 60)} min temu`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} h temu`;
    return `${Math.floor(diff / 86400)} d temu`;
  };

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="flex h-16 items-center justify-between border-b bg-background/80 backdrop-blur-xl px-4 lg:px-6 sticky top-0 z-30">
      {/* Left - Mobile menu */}
      <div className="flex items-center gap-4">
        <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
          <SheetTrigger asChild className="lg:hidden">
            <Button variant="ghost" size="icon" className="rounded-xl">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-72 border-r-0">
            <Sidebar onNavigate={() => setMobileMenuOpen(false)} />
          </SheetContent>
        </Sheet>

        {/* Breadcrumbs - could be dynamic */}
        <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
          <span className="hover:text-foreground cursor-pointer transition-colors">Home</span>
          <span>/</span>
          <span className="text-foreground font-medium">Dashboard</span>
        </div>
      </div>

      {/* Right - Actions */}
      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <Button 
          variant="ghost" 
          size="icon" 
          className="rounded-xl"
          onClick={toggleTheme}
        >
          {resolvedTheme === 'dark' ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        {/* Notifications */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="relative rounded-xl">
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 px-1 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground animate-pulse">
                  {unreadCount}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80" sideOffset={8}>
            <DropdownMenuLabel className="flex items-center justify-between">
              <span>Powiadomienia</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={async () => {
                  await notificationsApi.markAllRead();
                  refetchNotifications();
                }}
              >
                Oznacz wszystko
              </Button>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <div className="max-h-80 overflow-auto">
              {notifications.length ? notifications.map((n: any) => (
                <DropdownMenuItem
                  key={n.id}
                  className="cursor-pointer items-start gap-2 py-2"
                  onClick={async () => {
                    if (!n.is_read) {
                      await notificationsApi.markRead(n.id);
                      refetchNotifications();
                    }
                  }}
                >
                  <div className={cn('mt-1 h-2 w-2 rounded-full', n.is_read ? 'bg-muted' : 'bg-primary')} />
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{n.title}</p>
                    <p className="text-[11px] text-muted-foreground break-words">{n.message}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">{timeAgo(n.created_at)}</p>
                  </div>
                </DropdownMenuItem>
              )) : (
                <div className="p-3 text-xs text-muted-foreground">Brak powiadomień</div>
              )}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-2 px-2 rounded-xl">
              <Avatar className="h-8 w-8 ring-2 ring-primary/20">
                {profileData?.avatar_url ? <img src={profileData.avatar_url} alt="avatar" className="h-8 w-8 rounded-full object-cover" /> : null}
                <AvatarFallback className="bg-gradient-to-br from-primary to-primary/70 text-primary-foreground text-sm font-semibold">
                  {initials || 'U'}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:flex flex-col items-start">
                <span className="text-sm font-medium leading-tight">{profileData?.name || user?.name || 'Użytkownik'}</span>
                <span className="text-xs text-muted-foreground leading-tight">{user?.role || 'Agent'}</span>
              </div>
              <ChevronDown className="h-4 w-4 text-muted-foreground hidden sm:block" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64" sideOffset={8}>
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium">{profileData?.name || user?.name}</p>
                <p className="text-xs text-muted-foreground">{profileData?.email || user?.email}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate('/settings')} className="cursor-pointer">
              <User className="mr-2 h-4 w-4" />
              Profil
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate('/settings')} className="cursor-pointer">
              <Settings className="mr-2 h-4 w-4" />
              Ustawienia
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive focus:text-destructive">
              <LogOut className="mr-2 h-4 w-4" />
              Wyloguj
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

interface AppShellProps {
  children: ReactNode;
}

function MobileBottomNav() {
  const location = useLocation();

  const mobileNav = [
    { label: 'Start', path: '/', icon: LayoutDashboard },
    { label: 'Oferty', path: '/listings', icon: Home },
    { label: 'Kontakty', path: '/contacts', icon: Users },
    { label: 'Zadania', path: '/tasks', icon: CheckSquare },
    { label: 'Więcej', path: '/settings', icon: Settings },
  ];

  return (
    <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="grid grid-cols-5">
        {mobileNav.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
          return (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex flex-col items-center justify-center gap-1 py-2 text-[11px] min-w-0',
                isActive ? 'text-primary font-semibold' : 'text-muted-foreground'
              )}
            >
              <Icon className="h-4 w-4" />
              <span className="truncate max-w-full px-1">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen max-w-full overflow-hidden bg-background">
      {/* Sidebar - hidden on mobile */}
      <aside className="hidden lg:block w-72 flex-shrink-0">
        <Sidebar />
      </aside>

      {/* Main content area */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-auto p-3 sm:p-4 lg:p-8 pb-20 lg:pb-8">
          <div className="mx-auto max-w-7xl min-w-0">
            {children}
          </div>
        </main>
      </div>
      <MobileBottomNav />
    </div>
  );
}