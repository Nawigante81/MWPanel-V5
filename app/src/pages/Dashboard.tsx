import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  Home,
  Users,
  CheckSquare,
  TrendingUp,
  AlertCircle,
  Plus,
  ArrowRight,
  Calendar,
  Clock,
  Eye,
  MapPin,
  CheckCircle2,
} from 'lucide-react';

// Enhanced Stat Card with gradient and animation
interface StatCardProps {
  title: string;
  value: number | string;
  description?: string;
  icon: React.ElementType;
  href?: string;
  loading?: boolean;
  trend?: { value: number; positive: boolean };
  color?: 'blue' | 'green' | 'amber' | 'purple' | 'rose';
}

const colorVariants = {
  blue: 'from-blue-500/10 to-blue-600/5 text-blue-600 dark:text-blue-400',
  green: 'from-emerald-500/10 to-emerald-600/5 text-emerald-600 dark:text-emerald-400',
  amber: 'from-amber-500/10 to-amber-600/5 text-amber-600 dark:text-amber-400',
  purple: 'from-purple-500/10 to-purple-600/5 text-purple-600 dark:text-purple-400',
  rose: 'from-rose-500/10 to-rose-600/5 text-rose-600 dark:text-rose-400',
};

const iconBgVariants = {
  blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  green: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
  rose: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
};

function StatCard({
  title,
  value,
  description,
  icon: Icon,
  href,
  loading,
  trend,
  color = 'blue',
}: StatCardProps) {
  return (
    <Card className={cn(
      'card-hover overflow-hidden relative',
      'bg-gradient-to-br',
      colorVariants[color]
    )}>
      <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-white/5 to-transparent rounded-full -translate-y-1/2 translate-x-1/2" />
      <CardHeader className="flex flex-row items-center justify-between pb-2 relative">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div className={cn('p-2 rounded-xl', iconBgVariants[color])}>
          <Icon className="h-4 w-4" />
        </div>
      </CardHeader>
      <CardContent className="relative">
        {loading ? (
          <Skeleton className="h-10 w-24" />
        ) : (
          <>
            <div className="flex items-baseline gap-2">
              <div className="text-3xl font-bold tracking-tight number-display">{value}</div>
              {trend && (
                <Badge 
                  variant={trend.positive ? 'default' : 'destructive'}
                  className="text-[10px]"
                >
                  {trend.positive ? '+' : ''}{trend.value}%
                </Badge>
              )}
            </div>
            {description && (
              <p className="text-xs text-muted-foreground mt-1">{description}</p>
            )}
            {href && (
              <Link
                to={href}
                className={cn(
                  'mt-3 inline-flex items-center text-xs font-medium hover:underline transition-colors',
                  color === 'blue' && 'text-blue-600 dark:text-blue-400',
                  color === 'green' && 'text-emerald-600 dark:text-emerald-400',
                  color === 'amber' && 'text-amber-600 dark:text-amber-400',
                  color === 'purple' && 'text-purple-600 dark:text-purple-400',
                  color === 'rose' && 'text-rose-600 dark:text-rose-400',
                )}
              >
                Zobacz więcej <ArrowRight className="ml-1 h-3 w-3" />
              </Link>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// Activity Item Component
interface ActivityItemProps {
  icon: React.ElementType;
  title: string;
  description: string;
  time: string;
  color?: 'blue' | 'green' | 'amber' | 'purple' | 'rose' | 'gray';
}

function ActivityItem({ icon: Icon, title, description, time, color = 'blue' }: ActivityItemProps) {
  const colorClasses = {
    blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
    green: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
    rose: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
    gray: 'bg-muted text-muted-foreground',
  };

  return (
    <div className="flex items-start gap-3 py-3 group">
      <div className={cn('p-2 rounded-lg shrink-0', colorClasses[color])}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{title}</p>
        <p className="text-xs text-muted-foreground truncate">{description}</p>
      </div>
      <span className="text-xs text-muted-foreground shrink-0">{time}</span>
    </div>
  );
}

// Quick Action Button
interface QuickActionProps {
  icon: React.ElementType;
  label: string;
  description: string;
  href: string;
  color?: 'blue' | 'green' | 'amber' | 'purple';
}

function QuickAction({ icon: Icon, label, description, href, color = 'blue' }: QuickActionProps) {
  const colorClasses = {
    blue: 'hover:border-blue-500/50 hover:bg-blue-500/5',
    green: 'hover:border-emerald-500/50 hover:bg-emerald-500/5',
    amber: 'hover:border-amber-500/50 hover:bg-amber-500/5',
    purple: 'hover:border-purple-500/50 hover:bg-purple-500/5',
  };

  return (
    <Link
      to={href}
      className={cn(
        'flex items-center gap-4 p-4 rounded-xl border bg-card transition-all duration-200 group',
        colorClasses[color]
      )}
    >
      <div className={cn(
        'p-3 rounded-xl transition-colors',
        color === 'blue' && 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
        color === 'green' && 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
        color === 'amber' && 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
        color === 'purple' && 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
      )}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1">
        <p className="font-medium text-sm">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
    </Link>
  );
}

// Task Item Component
interface TaskItemProps {
  title: string;
  dueDate: string;
  priority: 'low' | 'medium' | 'high';
  completed?: boolean;
}

function TaskItem({ title, dueDate, priority, completed }: TaskItemProps) {
  const priorityColors = {
    low: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
    medium: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    high: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
  };

  return (
    <div className="flex items-center gap-3 py-2 group">
      <button className={cn(
        'h-5 w-5 rounded-full border-2 flex items-center justify-center transition-colors',
        completed 
          ? 'bg-primary border-primary text-primary-foreground' 
          : 'border-muted-foreground/30 hover:border-primary'
      )}>
        {completed && <CheckCircle2 className="h-3 w-3" />}
      </button>
      <div className="flex-1 min-w-0">
        <p className={cn('text-sm truncate', completed && 'line-through text-muted-foreground')}>{title}</p>
        <p className="text-xs text-muted-foreground flex items-center gap-1">
          <Clock className="h-3 w-3" /> {dueDate}
        </p>
      </div>
      <Badge variant="secondary" className={cn('text-[10px]', priorityColors[priority])}>
        {priority === 'high' ? 'Wysoki' : priority === 'medium' ? 'Średni' : 'Niski'}
      </Badge>
    </div>
  );
}

// Listing Preview Card
interface ListingPreviewProps {
  title: string;
  location: string;
  price: string;
  image?: string;
  status: string;
  views: number;
}

function ListingPreview({ title, location, price, status, views }: ListingPreviewProps) {
  const statusConfig: Record<string, { label: string; class: string }> = {
    active: { label: 'Aktywna', class: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' },
    published: { label: 'Opublikowana', class: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' },
    draft: { label: 'Szkic', class: 'bg-amber-500/10 text-amber-600 dark:text-amber-400' },
    inactive: { label: 'Nieaktywna', class: 'bg-gray-500/10 text-gray-600 dark:text-gray-400' },
    reserved: { label: 'Zarezerwowana', class: 'bg-purple-500/10 text-purple-600 dark:text-purple-400' },
    sold: { label: 'Sprzedana', class: 'bg-blue-500/10 text-blue-600 dark:text-blue-400' },
    rented: { label: 'Wynajęta', class: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400' },
    archived: { label: 'Archiwalna', class: 'bg-slate-500/10 text-slate-600 dark:text-slate-400' },
  };

  const resolvedStatus = statusConfig[status] || {
    label: status || 'Nieznany',
    class: 'bg-gray-500/10 text-gray-600 dark:text-gray-400',
  };

  return (
    <div className="flex items-center gap-4 py-3 group">
      <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-muted to-muted/50 flex items-center justify-center shrink-0">
        <Home className="h-6 w-6 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">{title}</p>
        <p className="text-xs text-muted-foreground flex items-center gap-1 truncate">
          <MapPin className="h-3 w-3 shrink-0" /> {location}
        </p>
        <div className="flex items-center gap-3 mt-1">
          <span className="text-sm font-semibold">{price}</span>
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Eye className="h-3 w-3" /> {views}
          </span>
        </div>
      </div>
      <Badge variant="secondary" className={cn('text-[10px] shrink-0', resolvedStatus.class)}>
        {resolvedStatus.label}
      </Badge>
    </div>
  );
}

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: dashboardApi.getStats,
    refetchInterval: 30000,
  });

  const { data: dashboardData } = useQuery({
    queryKey: ['dashboard-payload'],
    queryFn: dashboardApi.getDashboard,
    refetchInterval: 30000,
    enabled: !statsError,
  });

  const recentListings = dashboardData?.recent_offers || [];
  const pendingTasks = dashboardData?.pending_tasks || [];
  const listingsLoading = statsLoading && !dashboardData;
  const tasksLoading = statsLoading && !dashboardData;

  if (statsError) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground">Przegląd Twojego biura nieruchomości</p>
          </div>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Nie udało się pobrać danych. Spróbuj odświeżyć stronę.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const { data: activities = [] } = useQuery({
    queryKey: ['dashboard-activity'],
    queryFn: dashboardApi.getRecentActivity,
    refetchInterval: 30000,
    enabled: !statsError,
  });

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Przegląd Twojego biura nieruchomości</p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" className="rounded-xl">
            <Link to="/listings/new">
              <Plus className="mr-2 h-4 w-4" />
              Nowa oferta
            </Link>
          </Button>
          <Button asChild className="rounded-xl">
            <Link to="/contacts">
              <Plus className="mr-2 h-4 w-4" />
              Nowy kontakt
            </Link>
          </Button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Wszystkie oferty"
          value={stats?.total_listings || 0}
          description={`${stats?.active_listings || 0} aktywnych`}
          icon={Home}
          href="/listings"
          loading={statsLoading}
          trend={{ value: 12, positive: true }}
          color="blue"
        />
        <StatCard
          title="Kontakty"
          value={stats?.total_contacts || 0}
          description="Aktywni klienci"
          icon={Users}
          href="/contacts"
          loading={statsLoading}
          trend={{ value: 8, positive: true }}
          color="green"
        />
        <StatCard
          title="Zadania do wykonania"
          value={stats?.pending_tasks || 0}
          description={`${stats?.overdue_tasks || 0} przeterminowanych`}
          icon={CheckSquare}
          href="/tasks"
          loading={statsLoading}
          color="amber"
        />
        <StatCard
          title="Nowe oferty (tydzień)"
          value={stats?.new_this_week || 0}
          description="W tym miesiącu: 24"
          icon={TrendingUp}
          href="/listings"
          loading={statsLoading}
          trend={{ value: 23, positive: true }}
          color="purple"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column - 2/3 width */}
        <div className="lg:col-span-2 space-y-6">
          {/* Quick Actions */}
          <Card className="card-hover">
            <CardHeader>
              <CardTitle className="text-lg">Szybkie akcje</CardTitle>
              <CardDescription>Najczęściej używane funkcje</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <QuickAction
                icon={Home}
                label="Przeglądaj oferty"
                description="Zarządzaj nieruchomościami"
                href="/listings"
                color="blue"
              />
              <QuickAction
                icon={Users}
                label="Zarządzaj kontaktami"
                description="Baza klientów i partnerów"
                href="/contacts"
                color="green"
              />
              <QuickAction
                icon={CheckSquare}
                label="Zobacz zadania"
                description={`${stats?.pending_tasks || 0} oczekujących zadań`}
                href="/tasks"
                color="amber"
              />
              <QuickAction
                icon={Calendar}
                label="Kalendarz"
                description="Spotkania i terminy"
                href="/calendar"
                color="purple"
              />
            </CardContent>
          </Card>

          {/* Recent Listings */}
          <Card className="card-hover">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg">Ostatnie oferty</CardTitle>
                <CardDescription>Najnowsze nieruchomości w systemie</CardDescription>
              </div>
              <Button asChild variant="ghost" size="sm" className="rounded-lg">
                <Link to="/listings">
                  Wszystkie <ArrowRight className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              {listingsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : recentListings && recentListings.length > 0 ? (
                <div className="divide-y">
                  {recentListings.slice(0, 3).map((listing: any) => (
                    <ListingPreview
                      key={listing.id}
                      title={listing.title}
                      location={`${listing.city || listing.region || '-'}${listing.district ? `, ${listing.district}` : ''}`}
                      price={`${Number(listing.price || 0).toLocaleString('pl-PL')} PLN`}
                      status={listing.status}
                      views={listing.views || Math.floor(Math.random() * 500)}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Home className="h-12 w-12 mx-auto mb-3 opacity-30" />
                  <p>Brak ofert do wyświetlenia</p>
                  <Button asChild variant="outline" className="mt-4 rounded-xl">
                    <Link to="/listings/new">Dodaj pierwszą ofertę</Link>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column - 1/3 width */}
        <div className="space-y-6">
          {/* Pending Tasks */}
          <Card className="card-hover">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg">Zadania</CardTitle>
                <CardDescription>Do wykonania</CardDescription>
              </div>
              <Button asChild variant="ghost" size="sm" className="rounded-lg">
                <Link to="/tasks">
                  Wszystkie <ArrowRight className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </CardHeader>
            <CardContent>
              {tasksLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : pendingTasks && pendingTasks.length > 0 ? (
                <div className="divide-y">
                  {pendingTasks.slice(0, 5).map((task: any) => (
                    <TaskItem
                      key={task.id}
                      title={task.title}
                      dueDate={task.due_date ? new Date(task.due_date).toLocaleDateString('pl-PL') : 'Bez terminu'}
                      priority={task.priority || 'medium'}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-3 opacity-30" />
                  <p>Brak oczekujących zadań</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card className="card-hover">
            <CardHeader>
              <CardTitle className="text-lg">Ostatnia aktywność</CardTitle>
              <CardDescription>Co działo się ostatnio</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="divide-y">
                {activities.length ? activities.map((activity: any, index: number) => {
                  const ts = activity.created_at ? new Date(activity.created_at) : null;
                  const time = ts ? ts.toLocaleString('pl-PL') : '-';
                  return (
                    <ActivityItem
                      key={activity.id || index}
                      icon={activity.type?.includes('task') ? CheckSquare : activity.type?.includes('contact') ? Users : Home}
                      title={activity.title || 'Aktywność'}
                      description={activity.description || '-'}
                      time={time}
                      color={activity.type?.includes('delete') ? 'rose' : 'blue'}
                    />
                  );
                }) : (
                  <div className="py-6 text-sm text-muted-foreground">Brak aktywności.</div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Performance Card */}
          <Card className="card-hover bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                Wydajność
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Cel miesięczny</span>
                  <span className="font-medium">75%</span>
                </div>
                <Progress value={75} className="h-2" />
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Konwersja leadów</span>
                  <span className="font-medium">32%</span>
                </div>
                <Progress value={32} className="h-2" />
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Zadowolenie klientów</span>
                  <span className="font-medium">94%</span>
                </div>
                <Progress value={94} className="h-2" />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
