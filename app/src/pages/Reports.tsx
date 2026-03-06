import { useEffect, useState } from 'react';
import { 
  TrendingUp, 
  Users, 
  Home, 
  DollarSign, 
  Calendar,
  Download,
  BarChart3,
  PieChart,
  Activity,
  Target,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// Simple bar chart component
function SimpleBarChart({ data, color = 'blue' }: { data: number[]; color?: string }) {
  const max = Math.max(...data);
  const colorClasses = {
    blue: 'bg-blue-500',
    green: 'bg-emerald-500',
    amber: 'bg-amber-500',
    purple: 'bg-purple-500',
    rose: 'bg-rose-500',
  };

  return (
    <div className="flex items-end gap-2 h-32">
      {data.map((value, i) => (
        <div
          key={i}
          className="flex-1 flex flex-col items-center gap-1"
        >
          <div
            className={cn('w-full rounded-t-md transition-all duration-500', colorClasses[color as keyof typeof colorClasses])}
            style={{ height: `${(value / max) * 100}%` }}
          />
          <span className="text-xs text-muted-foreground">{i + 1}</span>
        </div>
      ))}
    </div>
  );
}

// Simple line chart component
function SimpleLineChart({ data }: { data: number[] }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((value, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 100 - ((value - min) / range) * 80 - 10;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="h-32 w-full relative">
      <svg viewBox="0 0 100 100" className="w-full h-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgb(59, 130, 246)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="rgb(59, 130, 246)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon
          points={`0,100 ${points} 100,100`}
          fill="url(#lineGradient)"
        />
        <polyline
          points={points}
          fill="none"
          stroke="rgb(59, 130, 246)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

// Simple donut chart
function SimpleDonutChart({ 
  data, 
  labels 
}: { 
  data: number[]; 
  labels: string[];
}) {
  const total = data.reduce((a, b) => a + b, 0);
  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#f43f5e'];
  
  let currentAngle = 0;
  const segments = data.map((value, i) => {
    const angle = (value / total) * 360;
    const startAngle = currentAngle;
    currentAngle += angle;
    return { startAngle, angle, color: colors[i % colors.length], value, label: labels[i] };
  });

  return (
    <div className="flex items-center gap-6">
      <div className="relative w-32 h-32">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          {segments.map((segment, i) => (
            <circle
              key={i}
              cx="50"
              cy="50"
              r="40"
              fill="none"
              stroke={segment.color}
              strokeWidth="20"
              strokeDasharray={`${(segment.angle / 360) * 251.2} 251.2`}
              strokeDashoffset={-((segment.startAngle / 360) * 251.2)}
              className="transition-all duration-500"
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold">{total}</span>
        </div>
      </div>
      <div className="space-y-2">
        {segments.map((segment, i) => (
          <div key={i} className="flex items-center gap-2 text-sm">
            <div 
              className="w-3 h-3 rounded-full" 
              style={{ backgroundColor: segment.color }}
            />
            <span className="text-muted-foreground">{segment.label}</span>
            <span className="font-medium">{segment.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface ReportStats {
  totalRevenue: number;
  revenueChange: number;
  totalSales: number;
  salesChange: number;
  avgCommission: number;
  commissionChange: number;
  conversionRate: number;
  conversionChange: number;
}

interface ChartData {
  monthlyRevenue: number[];
  monthlySales: number[];
  leadSources: { labels: string[]; values: number[] };
  agentPerformance: { name: string; sales: number; revenue: number }[];
  propertyTypes: { labels: string[]; values: number[] };
}

export default function Reports() {
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('month');
  const [stats, setStats] = useState<ReportStats | null>(null);
  const [chartData, setChartData] = useState<ChartData | null>(null);

  useEffect(() => {
    loadReports();
  }, [period]);

  async function loadReports() {
    try {
      setLoading(true);
      // Simulate API call with mock data
      await new Promise(resolve => setTimeout(resolve, 800));
      
      setStats({
        totalRevenue: 2458000,
        revenueChange: 18.5,
        totalSales: 47,
        salesChange: 12.3,
        avgCommission: 52298,
        commissionChange: 8.2,
        conversionRate: 34.2,
        conversionChange: 5.1,
      });

      setChartData({
        monthlyRevenue: [180, 220, 195, 240, 280, 320, 290, 350, 380, 420, 390, 450],
        monthlySales: [3, 4, 3, 5, 6, 7, 5, 8, 9, 10, 8, 11],
        leadSources: {
          labels: ['Portal', 'Polecenie', 'Social Media', 'Strona www', 'Inne'],
          values: [45, 28, 15, 8, 4],
        },
        agentPerformance: [
          { name: 'Anna Kowalska', sales: 15, revenue: 850000 },
          { name: 'Jan Nowak', sales: 12, revenue: 720000 },
          { name: 'Maria Wiśniewska', sales: 10, revenue: 580000 },
          { name: 'Piotr Zieliński', sales: 8, revenue: 308000 },
          { name: 'Katarzyna Lewandowska', sales: 2, revenue: 0 },
        ],
        propertyTypes: {
          labels: ['Mieszkania', 'Domy', 'Działki', 'Lokale', 'Garaże'],
          values: [52, 28, 12, 6, 2],
        },
      });
    } catch (error) {
      console.error('Error loading reports:', error);
    } finally {
      setLoading(false);
    }
  }

  function formatCurrency(value: number): string {
    return new Intl.NumberFormat('pl-PL', {
      style: 'currency',
      currency: 'PLN',
      maximumFractionDigits: 0,
    }).format(value);
  }

  const statCards = [
    {
      title: 'Przychody całkowite',
      value: stats ? formatCurrency(stats.totalRevenue) : '-',
      change: stats?.revenueChange || 0,
      icon: DollarSign,
      color: 'blue',
    },
    {
      title: 'Liczba transakcji',
      value: stats?.totalSales.toString() || '-',
      change: stats?.salesChange || 0,
      icon: Home,
      color: 'green',
    },
    {
      title: 'Średnia prowizja',
      value: stats ? formatCurrency(stats.avgCommission) : '-',
      change: stats?.commissionChange || 0,
      icon: Target,
      color: 'amber',
    },
    {
      title: 'Konwersja leadów',
      value: stats ? `${stats.conversionRate}%` : '-',
      change: stats?.conversionChange || 0,
      icon: TrendingUp,
      color: 'purple',
    },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Raporty i analizy</h1>
          <p className="text-muted-foreground">
            Szczegółowe statystyki i wskaźniki wydajności biura
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-40">
              <Calendar className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="week">Ostatni tydzień</SelectItem>
              <SelectItem value="month">Ostatni miesiąc</SelectItem>
              <SelectItem value="quarter">Ostatni kwartał</SelectItem>
              <SelectItem value="year">Ostatni rok</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Eksport
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat, index) => (
          <Card key={index} className="card-hover">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">
                    {stat.title}
                  </p>
                  <p className="text-2xl font-bold">{stat.value}</p>
                  <div className="flex items-center gap-1">
                    {stat.change >= 0 ? (
                      <ArrowUpRight className="w-4 h-4 text-emerald-500" />
                    ) : (
                      <ArrowDownRight className="w-4 h-4 text-rose-500" />
                    )}
                    <span className={cn(
                      'text-sm font-medium',
                      stat.change >= 0 ? 'text-emerald-500' : 'text-rose-500'
                    )}>
                      {Math.abs(stat.change)}%
                    </span>
                    <span className="text-sm text-muted-foreground">vs poprzedni okres</span>
                  </div>
                </div>
                <div className={cn(
                  'p-3 rounded-xl',
                  stat.color === 'blue' && 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
                  stat.color === 'green' && 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
                  stat.color === 'amber' && 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
                  stat.color === 'purple' && 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
                )}>
                  <stat.icon className="w-6 h-6" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">
            <BarChart3 className="w-4 h-4 mr-2" />
            Przegląd
          </TabsTrigger>
          <TabsTrigger value="agents">
            <Users className="w-4 h-4 mr-2" />
            Agenci
          </TabsTrigger>
          <TabsTrigger value="sources">
            <PieChart className="w-4 h-4 mr-2" />
            Źródła leadów
          </TabsTrigger>
          <TabsTrigger value="trends">
            <Activity className="w-4 h-4 mr-2" />
            Trendy
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Revenue Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Przychody miesięczne</CardTitle>
                <CardDescription>Wartość transakcji w tys. PLN</CardDescription>
              </CardHeader>
              <CardContent>
                {chartData && (
                  <>
                    <SimpleBarChart data={chartData.monthlyRevenue} color="blue" />
                    <div className="flex justify-between mt-4 text-sm text-muted-foreground">
                      <span>Sty</span>
                      <span>Mar</span>
                      <span>Maj</span>
                      <span>Lip</span>
                      <span>Wrz</span>
                      <span>Lis</span>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Sales Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Liczba transakcji</CardTitle>
                <CardDescription>Ilość zamkniętych deali miesięcznie</CardDescription>
              </CardHeader>
              <CardContent>
                {chartData && (
                  <>
                    <SimpleBarChart data={chartData.monthlySales} color="green" />
                    <div className="flex justify-between mt-4 text-sm text-muted-foreground">
                      <span>Sty</span>
                      <span>Mar</span>
                      <span>Maj</span>
                      <span>Lip</span>
                      <span>Wrz</span>
                      <span>Lis</span>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Property Types */}
          <Card>
            <CardHeader>
              <CardTitle>Struktura ofert</CardTitle>
              <CardDescription>Rozkład typów nieruchomości w portfolio</CardDescription>
            </CardHeader>
            <CardContent>
              {chartData && (
                <SimpleDonutChart 
                  data={chartData.propertyTypes.values} 
                  labels={chartData.propertyTypes.labels}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="agents" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Wydajność agentów</CardTitle>
              <CardDescription>Ranking agentów według liczby transakcji i przychodów</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {chartData?.agentPerformance.map((agent, i) => (
                  <div key={i} className="flex items-center gap-4">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-medium text-sm">
                      {i + 1}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium">{agent.name}</span>
                        <span className="text-sm text-muted-foreground">
                          {formatCurrency(agent.revenue)}
                        </span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full transition-all duration-500"
                          style={{ width: `${(agent.sales / 15) * 100}%` }}
                        />
                      </div>
                      <div className="flex justify-between mt-1 text-xs text-muted-foreground">
                        <span>{agent.sales} transakcji</span>
                        <span>{Math.round((agent.sales / 15) * 100)}% celu</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sources" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Źródła pozyskiwania leadów</CardTitle>
              <CardDescription>Skąd pochodzą Twoi klienci</CardDescription>
            </CardHeader>
            <CardContent>
              {chartData && (
                <SimpleDonutChart 
                  data={chartData.leadSources.values} 
                  labels={chartData.leadSources.labels}
                />
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-3">
            {chartData?.leadSources.labels.map((label, i) => (
              <Card key={i} className="card-hover">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{label}</span>
                    <Badge variant="secondary">{chartData.leadSources.values[i]}</Badge>
                  </div>
                  <div className="mt-2 text-2xl font-bold">
                    {Math.round((chartData.leadSources.values[i] / chartData.leadSources.values.reduce((a, b) => a + b, 0)) * 100)}%
                  </div>
                  <p className="text-sm text-muted-foreground">udział w leadach</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Trend przychodów</CardTitle>
              <CardDescription>Dynamika wzrostu w czasie</CardDescription>
            </CardHeader>
            <CardContent>
              {chartData && <SimpleLineChart data={chartData.monthlyRevenue} />}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
