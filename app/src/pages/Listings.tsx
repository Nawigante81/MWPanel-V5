import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { listingsApi, scrapeApi, sourcesApi } from '@/lib/api';
import type { Listing } from '@/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import {
  Search,
  Plus,
  MoreVertical,
  MapPin,
  AlertCircle,
  Eye,
  Edit,
  CheckCircle,
  XCircle,
  Building2,
  BedDouble,
  Maximize,
  Calendar,
  Filter,
  Grid3X3,
  List,
  Heart,
  Share2,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const statusLabels: Record<string, string> = {
  draft: 'Szkic',
  published: 'Opublikowana',
  archived: 'Archiwalna',
  rented: 'Wynajęta',
  sold: 'Sprzedana',
  active: 'Aktywna',
  inactive: 'Nieaktywna',
  reserved: 'Zarezerwowana',
};

const statusConfig: Record<string, { label: string; class: string; dot: string }> = {
  draft: {
    label: 'Szkic',
    class: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20',
    dot: 'bg-slate-500'
  },
  published: {
    label: 'Opublikowana',
    class: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    dot: 'bg-emerald-500'
  },
  archived: {
    label: 'Archiwalna',
    class: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20',
    dot: 'bg-gray-400'
  },
  rented: {
    label: 'Wynajęta',
    class: 'bg-violet-500/10 text-violet-600 dark:text-violet-400 border-violet-500/20',
    dot: 'bg-violet-500'
  },
  sold: {
    label: 'Sprzedana',
    class: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
    dot: 'bg-blue-500'
  },
  active: {
    label: 'Aktywna',
    class: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    dot: 'bg-emerald-500'
  },
  inactive: {
    label: 'Nieaktywna',
    class: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20',
    dot: 'bg-gray-400'
  },
  reserved: {
    label: 'Zarezerwowana',
    class: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    dot: 'bg-amber-500'
  },
};

const propertyTypeLabels: Record<string, string> = {
  apartment: 'Mieszkanie',
  house: 'Dom',
  commercial: 'Lokal użytkowy',
  land: 'Działka',
  garage: 'Garaż',
};

function ListingCard({ listing, view = 'list' }: { listing: Listing; view?: 'list' | 'grid' }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: Listing['status'] }) =>
      listingsApi.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      toast.success('Status zaktualizowany');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd aktualizacji statusu');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => listingsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      toast.success('Oferta została usunięta');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd usuwania oferty');
    },
  });

  const handleStatusChange = (status: Listing['status']) => {
    updateStatusMutation.mutate({ id: listing.id, status });
  };

  const handleDelete = () => {
    if (confirm('Czy na pewno chcesz usunąć tę ofertę?')) {
      deleteMutation.mutate(listing.id);
    }
  };

  if (view === 'grid') {
    return (
      <Card className="card-hover overflow-hidden group">
        {/* Image */}
        <div className="relative h-48 bg-gradient-to-br from-muted to-muted/50 overflow-hidden">
          {listing.images && listing.images.length > 0 ? (
            <img 
              src={listing.images[0]} 
              alt={listing.title}
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <Building2 className="h-16 w-16 text-muted-foreground/30" />
            </div>
          )}
          <div className="absolute top-3 left-3">
            <Badge variant="secondary" className={cn('text-[10px] font-medium', (statusConfig[listing.status] || statusConfig.published).class)}>
              <span className={cn('w-1.5 h-1.5 rounded-full mr-1.5', (statusConfig[listing.status] || statusConfig.published).dot)} />
              {statusLabels[listing.status]}
            </Badge>
          </div>
          <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button variant="secondary" size="icon" className="h-8 w-8 rounded-full bg-background/80 backdrop-blur">
              <Heart className="h-4 w-4" />
            </Button>
            <Button variant="secondary" size="icon" className="h-8 w-8 rounded-full bg-background/80 backdrop-blur">
              <Share2 className="h-4 w-4" />
            </Button>
          </div>
          <div className="absolute bottom-3 left-3 right-3">
            <div className="flex items-center justify-between">
              <Badge variant="secondary" className="bg-background/80 backdrop-blur text-[10px]">
                {propertyTypeLabels[listing.property_type] || listing.property_type}
              </Badge>
              <span className="text-sm font-semibold bg-background/80 backdrop-blur px-2 py-1 rounded-md">
                {listing.price != null ? `${listing.price.toLocaleString('pl-PL')} ${listing.currency}` : 'Cena do uzgodnienia'}
              </span>
            </div>
          </div>
        </div>
        
        <CardContent className="p-4">
          <h3 className="font-semibold text-base truncate mb-1 group-hover:text-primary transition-colors">
            {listing.title}
          </h3>
          <p className="text-sm text-muted-foreground flex items-center gap-1 mb-3">
            <MapPin className="h-3.5 w-3.5" />
            {listing.city || listing.region || '-'}{listing.district ? `, ${listing.district}` : ''}{listing.region && listing.city ? `, ${listing.region}` : ''}
          </p>
          
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {listing.rooms && (
              <span className="flex items-center gap-1">
                <BedDouble className="h-3.5 w-3.5" />
                {listing.rooms} pok.
              </span>
            )}
            {listing.area_sqm && (
              <span className="flex items-center gap-1">
                <Maximize className="h-3.5 w-3.5" />
                {listing.area_sqm} m²
              </span>
            )}
          </div>
          
          <Separator className="my-3" />
          
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {new Date(listing.created_at).toLocaleDateString('pl-PL')}
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => navigate(`/listings/${listing.id}`)}>
                  <Eye className="mr-2 h-4 w-4" />
                  Szczegóły
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => navigate(`/listings/${listing.id}/edit`)}>
                  <Edit className="mr-2 h-4 w-4" />
                  Edytuj
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleStatusChange('sold')}>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Oznacz jako sprzedane
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleStatusChange('archived')}>
                  <XCircle className="mr-2 h-4 w-4" />
                  Archiwizuj
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleDelete} className="text-destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Usuń
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="card-hover group">
      <CardContent className="p-0">
        <div className="flex flex-col sm:flex-row">
          {/* Image */}
          <div className="relative w-full sm:w-48 h-40 sm:h-auto min-h-[160px] bg-gradient-to-br from-muted to-muted/50 flex-shrink-0 overflow-hidden">
            {listing.images && listing.images.length > 0 ? (
              <img 
                src={listing.images[0]} 
                alt={listing.title}
                className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                <Building2 className="h-12 w-12 text-muted-foreground/30" />
              </div>
            )}
            <div className="absolute top-3 left-3">
              <Badge variant="secondary" className={cn('text-[10px] font-medium', (statusConfig[listing.status] || statusConfig.published).class)}>
                <span className={cn('w-1.5 h-1.5 rounded-full mr-1.5', (statusConfig[listing.status] || statusConfig.published).dot)} />
                {statusLabels[listing.status]}
              </Badge>
            </div>
          </div>
          
          {/* Content */}
          <div className="flex-1 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="text-[10px]">
                    {propertyTypeLabels[listing.property_type] || listing.property_type}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {listing.transaction_type === 'sale' ? 'Sprzedaż' : 'Wynajem'}
                  </span>
                </div>
                
                <h3 className="font-semibold text-lg truncate group-hover:text-primary transition-colors">
                  {listing.title}
                </h3>
                
                <p className="text-sm text-muted-foreground flex items-center gap-1 mt-1">
                  <MapPin className="h-3.5 w-3.5" />
                  {listing.city || listing.region || '-'}{listing.district ? `, ${listing.district}` : ''}{listing.region && listing.city ? `, ${listing.region}` : ''}
                </p>
                
                <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-muted-foreground">
                  {listing.rooms && (
                    <span className="flex items-center gap-1">
                      <BedDouble className="h-4 w-4" />
                      {listing.rooms} pok.
                    </span>
                  )}
                  {listing.area_sqm && (
                    <span className="flex items-center gap-1">
                      <Maximize className="h-4 w-4" />
                      {listing.area_sqm} m²
                    </span>
                  )}
                </div>
              </div>
              
              <div className="text-right">
                <p className="text-xl font-bold text-primary">
                  {listing.price != null ? `${listing.price.toLocaleString('pl-PL')} ${listing.currency}` : 'Cena do uzgodnienia'}
                </p>
                {listing.area_sqm && listing.price != null && (
                  <p className="text-xs text-muted-foreground">
                    {Math.round(listing.price / listing.area_sqm).toLocaleString('pl-PL')} {listing.currency}/m²
                  </p>
                )}
              </div>
            </div>
            
            <Separator className="my-3" />
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" />
                  {new Date(listing.created_at).toLocaleDateString('pl-PL')}
                </span>
                {listing.source && (
                  <span>Źródło: {listing.source}</span>
                )}
              </div>
              
              <div className="flex items-center gap-1">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-8 rounded-lg"
                  onClick={() => navigate(`/listings/${listing.id}`)}
                >
                  <Eye className="mr-1 h-4 w-4" />
                  Szczegóły
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => navigate(`/listings/${listing.id}/edit`)}>
                      <Edit className="mr-2 h-4 w-4" />
                      Edytuj
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleStatusChange('sold')}>
                      <CheckCircle className="mr-2 h-4 w-4" />
                      Oznacz jako sprzedane
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleStatusChange('archived')}>
                      <XCircle className="mr-2 h-4 w-4" />
                      Archiwizuj
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={handleDelete} className="text-destructive">
                      <Trash2 className="mr-2 h-4 w-4" />
                      Usuń
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ListingsSkeleton({ view = 'list' }: { view?: 'list' | 'grid' }) {
  if (view === 'grid') {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <Card key={i} className="overflow-hidden">
            <Skeleton className="h-48 w-full" />
            <CardContent className="p-4 space-y-3">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-4 w-1/3" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardContent className="p-0">
            <div className="flex flex-col sm:flex-row">
              <Skeleton className="w-full sm:w-48 h-40 sm:h-auto" />
              <div className="flex-1 p-4 space-y-3">
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-1/3" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function Listings() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [regionFilter, setRegionFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('newest');
  const [view, setView] = useState<'list' | 'grid'>('list');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [datePreset, setDatePreset] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const queryClient = useQueryClient();

  const toISODate = (d: Date) => {
    const y = d.getFullYear();
    const m = `${d.getMonth() + 1}`.padStart(2, '0');
    const day = `${d.getDate()}`.padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  const resolveDateRange = () => {
    if (datePreset === 'custom') {
      return { from: dateFrom || undefined, to: dateTo || undefined };
    }

    const now = new Date();
    const start = new Date(now);
    const end = new Date(now);

    if (datePreset === 'today') {
      return { from: toISODate(start), to: toISODate(end) };
    }
    if (datePreset === 'yesterday') {
      start.setDate(start.getDate() - 1);
      end.setDate(end.getDate() - 1);
      return { from: toISODate(start), to: toISODate(end) };
    }
    if (datePreset === 'last3') {
      start.setDate(start.getDate() - 2);
      return { from: toISODate(start), to: toISODate(end) };
    }
    if (datePreset === 'last7') {
      start.setDate(start.getDate() - 6);
      return { from: toISODate(start), to: toISODate(end) };
    }
    if (datePreset === 'last30') {
      start.setDate(start.getDate() - 29);
      return { from: toISODate(start), to: toISODate(end) };
    }

    return { from: undefined, to: undefined };
  };

  const dateRange = resolveDateRange();

  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: () => sourcesApi.getAll(),
  });

  const { data: listingsPage, isLoading, error } = useQuery({
    queryKey: ['listings-page', { page, pageSize, statusFilter, sourceFilter, regionFilter, search, sortBy, datePreset, dateFrom, dateTo }],
    queryFn: () => listingsApi.getPage({
      page,
      limit: pageSize,
      status: statusFilter === 'all' ? undefined : statusFilter,
      source: sourceFilter === 'all' ? undefined : sourceFilter,
      region: regionFilter === 'all' ? undefined : regionFilter,
      search: search || undefined,
      sort: 'date',
      order: sortBy === 'oldest' ? 'asc' : 'desc',
      date_from: dateRange.from,
      date_to: dateRange.to,
    }),
  });

  const { data: statsData } = useQuery({
    queryKey: ['listings-stats', { sourceFilter }],
    queryFn: () => listingsApi.getCounts({ source: sourceFilter === 'all' ? undefined : sourceFilter }),
  });

  useEffect(() => {
    setPage(1);
  }, [statusFilter, typeFilter, regionFilter, sourceFilter, search, pageSize, sortBy, datePreset, dateFrom, dateTo]);

  const manualScrapeMutation = useMutation({
    mutationFn: () => scrapeApi.trigger(),
    onSuccess: (res: any) => {
      toast.success(`Wymuszono sprawdzanie ogłoszeń (${res?.count || 0} źródła)`);
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (e: any) => toast.error(e.message || 'Nie udało się uruchomić sprawdzania'),
  });

  const listings = listingsPage?.data || [];

  const filteredListingsBase = listings.filter((listing) => {
    const matchesType = typeFilter === 'all' ? true : listing.property_type === typeFilter;
    return matchesType;
  });

  const regions = Array.from(new Set(listings.map((l) => l.region).filter(Boolean) as string[])).sort((a, b) => a.localeCompare(b, 'pl'));

  const filteredListings = [...filteredListingsBase].sort((a, b) => {
    if (sortBy === 'price_asc') return (a.price || 0) - (b.price || 0);
    if (sortBy === 'price_desc') return (b.price || 0) - (a.price || 0);
    if (sortBy === 'region_asc') return (a.region || '').localeCompare((b.region || ''), 'pl');
    if (sortBy === 'region_desc') return (b.region || '').localeCompare((a.region || ''), 'pl');
    if (sortBy === 'oldest') return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  const stats = {
    total: statsData?.total || 0,
    active: statsData?.active || 0,
    sold: statsData?.sold || 0,
    reserved: statsData?.reserved || 0,
  };

  const total = listingsPage?.total || 0;
  const pages = listingsPage?.pages || Math.ceil(total / pageSize) || 1;

  useEffect(() => {
    if (page > Math.max(pages, 1)) {
      setPage(Math.max(pages, 1));
    }
  }, [page, pages]);

  if (error) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Oferty</h1>
            <p className="text-muted-foreground">Zarządzaj nieruchomościami w systemie</p>
          </div>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Nie udało się pobrać ofert. Spróbuj odświeżyć stronę.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Oferty</h1>
          <p className="text-muted-foreground">Zarządzaj nieruchomościami w systemie</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <Button
            variant="outline"
            className="rounded-xl w-full sm:w-auto"
            onClick={() => manualScrapeMutation.mutate()}
            disabled={manualScrapeMutation.isPending}
          >
            <RefreshCw className={cn('mr-2 h-4 w-4', manualScrapeMutation.isPending && 'animate-spin')} />
            {manualScrapeMutation.isPending ? 'Sprawdzam...' : 'Sprawdź ogłoszenia teraz'}
          </Button>
          <Button asChild className="rounded-xl w-full sm:w-auto">
            <Link to="/listings/new">
              <Plus className="mr-2 h-4 w-4" />
              Nowa oferta
            </Link>
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="card-hover bg-gradient-to-br from-blue-500/10 to-blue-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Wszystkie</p>
            <p className="text-2xl font-bold">{stats.total}</p>
          </CardContent>
        </Card>
        <Card className="card-hover bg-gradient-to-br from-emerald-500/10 to-emerald-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Aktywne</p>
            <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{stats.active}</p>
          </CardContent>
        </Card>
        <Card className="card-hover bg-gradient-to-br from-amber-500/10 to-amber-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Zarezerwowane</p>
            <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">{stats.reserved}</p>
          </CardContent>
        </Card>
        <Card className="card-hover bg-gradient-to-br from-blue-500/10 to-blue-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Sprzedane</p>
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{stats.sold}</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="card-hover">
        <CardContent className="p-4 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Szukaj ofert..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 rounded-xl"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            {[
              { value: 'all', label: 'Wszystko' },
              { value: 'today', label: 'Dzisiaj' },
              { value: 'yesterday', label: 'Wczoraj' },
              { value: 'last3', label: '3 dni' },
              { value: 'last7', label: '7 dni' },
              { value: 'last30', label: '30 dni' },
              { value: 'custom', label: 'Zakres' },
            ].map((p) => (
              <Button
                key={p.value}
                type="button"
                variant={datePreset === p.value ? 'secondary' : 'outline'}
                size="sm"
                className="rounded-xl"
                onClick={() => setDatePreset(p.value)}
              >
                {p.label}
              </Button>
            ))}
          </div>

          {datePreset === 'custom' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-xl" />
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-xl" />
            </div>
          )}

          <div className="hidden md:flex flex-wrap gap-2">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full md:w-40 rounded-xl"><Filter className="h-4 w-4 mr-2" /><SelectValue placeholder="Status" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Wszystkie statusy</SelectItem>
                <SelectItem value="active">Aktywne</SelectItem>
                <SelectItem value="sold">Sprzedane</SelectItem>
                <SelectItem value="withdrawn">Wycofane</SelectItem>
                <SelectItem value="expired">Wygasłe</SelectItem>
                <SelectItem value="price_changed">Zmiana ceny</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="w-full md:w-44 rounded-xl"><SelectValue placeholder="Źródło" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Wszystkie źródła</SelectItem>
                {(sources || []).map((s: any) => (<SelectItem key={s.id} value={s.name}>{s.name}</SelectItem>))}
              </SelectContent>
            </Select>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-full md:w-40 rounded-xl"><Building2 className="h-4 w-4 mr-2" /><SelectValue placeholder="Typ" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Wszystkie typy</SelectItem><SelectItem value="apartment">Mieszkanie</SelectItem><SelectItem value="house">Dom</SelectItem><SelectItem value="commercial">Lokal użytkowy</SelectItem><SelectItem value="land">Działka</SelectItem><SelectItem value="garage">Garaż</SelectItem>
              </SelectContent>
            </Select>
            <Select value={regionFilter} onValueChange={setRegionFilter}>
              <SelectTrigger className="w-full md:w-48 rounded-xl"><MapPin className="h-4 w-4 mr-2" /><SelectValue placeholder="Województwo" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Wszystkie województwa</SelectItem>
                {regions.map((region) => (<SelectItem key={region} value={region}>{region}</SelectItem>))}
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-full md:w-52 rounded-xl"><SelectValue placeholder="Sortowanie" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">Data: najnowsze → najstarsze</SelectItem><SelectItem value="oldest">Data: najstarsze → najnowsze</SelectItem><SelectItem value="price_desc">Cena: malejąco</SelectItem><SelectItem value="price_asc">Cena: rosnąco</SelectItem><SelectItem value="region_asc">Województwo: A-Z</SelectItem><SelectItem value="region_desc">Województwo: Z-A</SelectItem>
              </SelectContent>
            </Select>
            <Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}>
              <SelectTrigger className="w-full md:w-36 rounded-xl"><SelectValue placeholder="Na stronę" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="20">20 / str.</SelectItem>
                <SelectItem value="50">50 / str.</SelectItem>
                <SelectItem value="100">100 / str.</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between gap-2">
            <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" className="md:hidden rounded-xl">
                  <Filter className="h-4 w-4 mr-2" /> Filtry
                </Button>
              </SheetTrigger>
              <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto">
                <SheetHeader><SheetTitle>Filtry ofert</SheetTitle></SheetHeader>
                <div className="mt-4 grid gap-3">
                  <Select value={statusFilter} onValueChange={setStatusFilter}><SelectTrigger className="w-full rounded-xl"><SelectValue placeholder="Status" /></SelectTrigger><SelectContent><SelectItem value="all">Wszystkie statusy</SelectItem><SelectItem value="active">Aktywne</SelectItem><SelectItem value="sold">Sprzedane</SelectItem><SelectItem value="withdrawn">Wycofane</SelectItem><SelectItem value="expired">Wygasłe</SelectItem><SelectItem value="price_changed">Zmiana ceny</SelectItem></SelectContent></Select>
                  <Select value={sourceFilter} onValueChange={setSourceFilter}><SelectTrigger className="w-full rounded-xl"><SelectValue placeholder="Źródło" /></SelectTrigger><SelectContent><SelectItem value="all">Wszystkie źródła</SelectItem>{(sources || []).map((s: any) => (<SelectItem key={s.id} value={s.name}>{s.name}</SelectItem>))}</SelectContent></Select>
                  <Select value={datePreset} onValueChange={setDatePreset}><SelectTrigger className="w-full rounded-xl"><SelectValue placeholder="Okres" /></SelectTrigger><SelectContent><SelectItem value="all">Wszystko</SelectItem><SelectItem value="today">Dzisiaj</SelectItem><SelectItem value="yesterday">Wczoraj</SelectItem><SelectItem value="last3">Ostatnie 3 dni</SelectItem><SelectItem value="last7">Ostatnie 7 dni</SelectItem><SelectItem value="last30">Ostatnie 30 dni</SelectItem><SelectItem value="custom">Zakres dat</SelectItem></SelectContent></Select>
                  {datePreset === 'custom' && (<><Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="rounded-xl" /><Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="rounded-xl" /></>)}
                  <Select value={typeFilter} onValueChange={setTypeFilter}><SelectTrigger className="w-full rounded-xl"><SelectValue placeholder="Typ" /></SelectTrigger><SelectContent><SelectItem value="all">Wszystkie typy</SelectItem><SelectItem value="apartment">Mieszkanie</SelectItem><SelectItem value="house">Dom</SelectItem><SelectItem value="commercial">Lokal użytkowy</SelectItem><SelectItem value="land">Działka</SelectItem><SelectItem value="garage">Garaż</SelectItem></SelectContent></Select>
                  <Select value={regionFilter} onValueChange={setRegionFilter}><SelectTrigger className="w-full rounded-xl"><SelectValue placeholder="Województwo" /></SelectTrigger><SelectContent><SelectItem value="all">Wszystkie województwa</SelectItem>{regions.map((region) => (<SelectItem key={region} value={region}>{region}</SelectItem>))}</SelectContent></Select>
                  <Select value={sortBy} onValueChange={setSortBy}><SelectTrigger className="w-full rounded-xl"><SelectValue placeholder="Sortowanie" /></SelectTrigger><SelectContent><SelectItem value="newest">Data: najnowsze → najstarsze</SelectItem><SelectItem value="oldest">Data: najstarsze → najnowsze</SelectItem><SelectItem value="price_desc">Cena: malejąco</SelectItem><SelectItem value="price_asc">Cena: rosnąco</SelectItem><SelectItem value="region_asc">Województwo: A-Z</SelectItem><SelectItem value="region_desc">Województwo: Z-A</SelectItem></SelectContent></Select>
                  <Select value={String(pageSize)} onValueChange={(v) => setPageSize(Number(v))}><SelectTrigger className="w-full rounded-xl"><SelectValue placeholder="Na stronę" /></SelectTrigger><SelectContent><SelectItem value="20">20 / str.</SelectItem><SelectItem value="50">50 / str.</SelectItem><SelectItem value="100">100 / str.</SelectItem></SelectContent></Select>
                </div>
              </SheetContent>
            </Sheet>

            <div className="flex items-center border rounded-xl overflow-hidden ml-auto">
              <Button variant={view === 'list' ? 'secondary' : 'ghost'} size="icon" className="h-10 w-10 rounded-none" onClick={() => setView('list')}><List className="h-4 w-4" /></Button>
              <Button variant={view === 'grid' ? 'secondary' : 'ghost'} size="icon" className="h-10 w-10 rounded-none" onClick={() => setView('grid')}><Grid3X3 className="h-4 w-4" /></Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Listings */}
      {isLoading ? (
        <ListingsSkeleton view={view} />
      ) : filteredListings.length === 0 ? (
        <Card className="card-hover">
          <CardContent className="p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
              <Building2 className="h-10 w-10 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Brak ofert</h3>
            <p className="text-muted-foreground mb-4 max-w-md mx-auto">
              {search || statusFilter !== 'all' || typeFilter !== 'all' || regionFilter !== 'all'
                ? 'Nie znaleziono ofert pasujących do wybranych filtrów'
                : 'Nie masz jeszcze żadnych ofert w systemie. Dodaj pierwszą ofertę, aby rozpocząć.'}
            </p>
            <Button asChild className="rounded-xl">
              <Link to="/listings/new">
                <Plus className="mr-2 h-4 w-4" />
                Dodaj ofertę
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className={cn(
          view === 'grid' 
            ? 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3' 
            : 'space-y-4'
        )}>
          {filteredListings.map((listing) => (
            <ListingCard key={listing.id} listing={listing} view={view} />
          ))}
        </div>
      )}

      {/* Pagination */}
      <Card className="card-hover">
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="text-sm text-muted-foreground">
            Strona {page} z {Math.max(pages, 1)} • rekordy {total === 0 ? 0 : ((page - 1) * pageSize + 1)}–{Math.min(page * pageSize, total)} z {total}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="rounded-xl"
              disabled={page <= 1 || isLoading}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
            >
              Previous
            </Button>
            <div className="text-sm min-w-16 text-center">{page}</div>
            <Button
              variant="outline"
              className="rounded-xl"
              disabled={page >= Math.max(pages, 1) || isLoading}
              onClick={() => setPage((p) => Math.min(p + 1, Math.max(pages, 1)))}
            >
              Next
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
