import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listingsApi, otodomApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
  ArrowLeft,
  Edit,
  MapPin,
  Building2,
  Bed,
  Calendar,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-react';
import { toast } from 'sonner';
import type { Listing } from '@/types';

const statusLabels: Record<string, string> = {
  active: 'Aktywna',
  inactive: 'Nieaktywna',
  reserved: 'Zarezerwowana',
  sold: 'Sprzedana',
};

const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-gray-100 text-gray-800',
  reserved: 'bg-yellow-100 text-yellow-800',
  sold: 'bg-blue-100 text-blue-800',
};

export default function ListingDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: listing, isLoading, error } = useQuery({
    queryKey: ['listing', id],
    queryFn: () => listingsApi.getById(id!),
    enabled: !!id,
  });

  const { data: otodomPublication, refetch: refetchOtodom } = useQuery({
    queryKey: ['otodom-publication', id],
    queryFn: () => otodomApi.getPublication(id!),
    enabled: !!id,
    retry: false,
  });

  const { data: otodomLogs } = useQuery({
    queryKey: ['otodom-logs', id],
    queryFn: () => otodomApi.getLogs(id!),
    enabled: !!id,
    retry: false,
  });

  const publishMutation = useMutation({
    mutationFn: () => otodomApi.publish(id!),
    onSuccess: () => {
      toast.success('Publikacja dodana do kolejki');
      refetchOtodom();
    },
    onError: (err: any) => toast.error(err.message || 'Błąd publikacji'),
  });

  const syncMutation = useMutation({
    mutationFn: () => otodomApi.sync(id!),
    onSuccess: () => {
      toast.success('Synchronizacja dodana do kolejki');
      refetchOtodom();
    },
    onError: (err: any) => toast.error(err.message || 'Błąd synchronizacji'),
  });

  const unpublishMutation = useMutation({
    mutationFn: () => otodomApi.unpublish(id!),
    onSuccess: () => {
      toast.success('Dezaktywacja dodana do kolejki');
      refetchOtodom();
    },
    onError: (err: any) => toast.error(err.message || 'Błąd zdejmowania oferty'),
  });

  const updateStatusMutation = useMutation({
    mutationFn: (status: Listing['status']) => listingsApi.updateStatus(id!, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listing', id] });
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      toast.success('Status zaktualizowany');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd aktualizacji statusu');
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/listings')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Skeleton className="h-8 w-64" />
        </div>
        <Card>
          <CardContent className="p-6 space-y-4">
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error || !listing) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/listings')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-3xl font-bold">Szczegóły oferty</h1>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Nie udało się pobrać szczegółów oferty. Spróbuj odświeżyć stronę.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/listings')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{listing.title}</h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <MapPin className="h-4 w-4" />
              {listing.city}{listing.district ? `, ${listing.district}` : ''}
              {listing.street && `, ${listing.street}`}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link to={`/listings/${id}/edit`}>
              <Edit className="mr-2 h-4 w-4" />
              Edytuj
            </Link>
          </Button>
          {listing.url && (
            <Button variant="outline" asChild>
              <a href={listing.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                Zobacz źródło
              </a>
            </Button>
          )}
        </div>
      </div>

      {/* Status & Price */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="text-3xl font-bold">
                {listing.price?.toLocaleString('pl-PL')} {listing.currency}
              </div>
              <Badge className={statusColors[listing.status]}>
                {statusLabels[listing.status]}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Zmień status:</span>
              <Select
                value={listing.status}
                onValueChange={(value) => updateStatusMutation.mutate(value as Listing['status'])}
              >
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">
                    <span className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-500" />
                      Aktywna
                    </span>
                  </SelectItem>
                  <SelectItem value="inactive">
                    <span className="flex items-center gap-2">
                      <XCircle className="h-4 w-4 text-gray-500" />
                      Nieaktywna
                    </span>
                  </SelectItem>
                  <SelectItem value="reserved">
                    <span className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-yellow-500" />
                      Zarezerwowana
                    </span>
                  </SelectItem>
                  <SelectItem value="sold">
                    <span className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-blue-500" />
                      Sprzedana
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Publikacja Otodom</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Status: {otodomPublication?.publication_status || 'Nieopublikowane'}</Badge>
            {otodomPublication?.external_listing_id ? (
              <Badge variant="outline">ID: {otodomPublication.external_listing_id}</Badge>
            ) : null}
            {otodomPublication?.attempts !== undefined ? (
              <Badge variant="outline">Próby: {otodomPublication.attempts}</Badge>
            ) : null}
          </div>

          {otodomPublication?.last_synced_at ? (
            <p className="text-sm text-muted-foreground">Ostatnia synchronizacja: {new Date(otodomPublication.last_synced_at).toLocaleString('pl-PL')}</p>
          ) : null}

          {otodomPublication?.last_error ? (
            <Alert variant="destructive">
              <AlertDescription>{otodomPublication.last_error}</AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => publishMutation.mutate()} disabled={publishMutation.isPending}>Publikuj do Otodom</Button>
            <Button variant="outline" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>Synchronizuj ponownie</Button>
            <Button variant="destructive" onClick={() => unpublishMutation.mutate()} disabled={unpublishMutation.isPending}>Zdejmij z Otodom</Button>
          </div>

          <div>
            <p className="text-sm font-medium mb-2">Logi publikacji</p>
            <div className="max-h-52 overflow-auto rounded border p-2 space-y-2 text-xs">
              {(otodomLogs?.logs || []).length ? (otodomLogs?.logs || []).map((l: any) => (
                <div key={l.id} className="border-b pb-1 last:border-0">
                  <div className="font-medium">{l.action}</div>
                  <div className="text-muted-foreground">{l.created_at}</div>
                  <div>{l?.changes?.message || JSON.stringify(l?.changes || {})}</div>
                </div>
              )) : <div className="text-muted-foreground">Brak logów</div>}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Details Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Szczegóły nieruchomości</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {listing.area_sqm && (
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Powierzchnia:</span>
                  <span className="font-medium">{listing.area_sqm} m²</span>
                </div>
              )}
              {listing.rooms && (
                <div className="flex items-center gap-2">
                  <Bed className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Pokoje:</span>
                  <span className="font-medium">{listing.rooms}</span>
                </div>
              )}
              {listing.floor !== undefined && (
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Piętro:</span>
                  <span className="font-medium">{listing.floor}</span>
                </div>
              )}
              {listing.year_built && (
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Rok budowy:</span>
                  <span className="font-medium">{listing.year_built}</span>
                </div>
              )}
            </div>
            <Separator />
            <div className="space-y-2">
              <span className="text-sm text-muted-foreground">Typ:</span>
              <div className="flex gap-2">
                <Badge variant="outline" className="capitalize">
                  {listing.property_type}
                </Badge>
                <Badge variant="outline">
                  {listing.transaction_type === 'sale' ? 'Sprzedaż' : 'Wynajem'}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Informacje dodatkowe</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {listing.source && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Źródło:</span>
                <span className="font-medium">{listing.source}</span>
              </div>
            )}
            {listing.commission_percent && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Prowizja:</span>
                <span className="font-medium">{listing.commission_percent}%</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Dodano:</span>
              <span className="font-medium">
                {new Date(listing.created_at).toLocaleDateString('pl-PL')}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Ostatnia aktualizacja:</span>
              <span className="font-medium">
                {new Date(listing.updated_at).toLocaleDateString('pl-PL')}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Description */}
      {listing.description && (
        <Card>
          <CardHeader>
            <CardTitle>Opis</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap">{listing.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Owner Info */}
      {(listing.owner_name || listing.owner_phone || listing.owner_email) && (
        <Card>
          <CardHeader>
            <CardTitle>Dane właściciela</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {listing.owner_name && (
              <div>
                <span className="text-sm text-muted-foreground">Imię i nazwisko:</span>
                <p className="font-medium">{listing.owner_name}</p>
              </div>
            )}
            {listing.owner_phone && (
              <div>
                <span className="text-sm text-muted-foreground">Telefon:</span>
                <p className="font-medium">{listing.owner_phone}</p>
              </div>
            )}
            {listing.owner_email && (
              <div>
                <span className="text-sm text-muted-foreground">Email:</span>
                <p className="font-medium">{listing.owner_email}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
