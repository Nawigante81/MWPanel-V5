import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { otodomApi, propertiesApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

export default function PropertyDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: property, isLoading } = useQuery({
    queryKey: ['property', id],
    queryFn: () => propertiesApi.getById(id!),
    enabled: !!id,
  });

  const { data: images = [] } = useQuery({
    queryKey: ['property-images', id],
    queryFn: () => propertiesApi.getImages(id!),
    enabled: !!id,
  });

  const { data: publication } = useQuery({
    queryKey: ['property-publication', id],
    queryFn: () => otodomApi.getPublication(id!),
    enabled: !!id,
  });

  const { data: logs } = useQuery({
    queryKey: ['property-publication-logs', id],
    queryFn: () => otodomApi.getLogs(id!),
    enabled: !!id,
  });

  const publish = useMutation({
    mutationFn: () => otodomApi.publish(id!),
    onSuccess: () => {
      toast.success('Publikacja dodana do kolejki');
      qc.invalidateQueries({ queryKey: ['property-publication', id] });
      qc.invalidateQueries({ queryKey: ['property-publication-logs', id] });
    },
    onError: (e: any) => toast.error(e.message || 'Błąd publikacji'),
  });

  const sync = useMutation({
    mutationFn: () => otodomApi.sync(id!),
    onSuccess: () => {
      toast.success('Synchronizacja dodana do kolejki');
      qc.invalidateQueries({ queryKey: ['property-publication', id] });
      qc.invalidateQueries({ queryKey: ['property-publication-logs', id] });
    },
    onError: (e: any) => toast.error(e.message || 'Błąd synchronizacji'),
  });

  const unpublish = useMutation({
    mutationFn: () => otodomApi.unpublish(id!),
    onSuccess: () => {
      toast.success('Zdjęcie z Otodom dodane do kolejki');
      qc.invalidateQueries({ queryKey: ['property-publication', id] });
      qc.invalidateQueries({ queryKey: ['property-publication-logs', id] });
    },
    onError: (e: any) => toast.error(e.message || 'Błąd zdejmowania'),
  });

  if (isLoading) return <div>Ładowanie...</div>;
  if (!property) return <div>Brak oferty</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/publications')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-bold">Property Details</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{property.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div>Status CRM: <Badge variant="outline">{property.crm_status}</Badge></div>
          <div>Miasto: {property.city || '-'}</div>
          <div>Cena: {property.price?.toLocaleString?.('pl-PL') || property.price} PLN</div>
          <div>Typ: {property.offer_type} / {property.property_type}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Publikacja Otodom</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{publication?.publication_status || 'not_published'}</Badge>
            {publication?.external_listing_id ? <Badge variant="outline">ID: {publication.external_listing_id}</Badge> : null}
            {publication?.attempts !== undefined ? <Badge variant="outline">Próby: {publication.attempts}</Badge> : null}
          </div>

          {publication?.last_error ? (
            <Alert variant="destructive"><AlertDescription>{publication.last_error}</AlertDescription></Alert>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => publish.mutate()} disabled={publish.isPending}>Publikuj</Button>
            <Button variant="outline" onClick={() => sync.mutate()} disabled={sync.isPending}>Synchronizuj</Button>
            <Button variant="destructive" onClick={() => unpublish.mutate()} disabled={unpublish.isPending}>Zdejmij</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Zdjęcia ({images.length})</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {images.map((img: any) => (
              <div key={img.id} className="border rounded overflow-hidden">
                <img src={img.file_url} alt="img" className="w-full h-28 object-cover" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Logi</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-xs">
          {(logs?.logs || []).map((l: any) => (
            <div key={l.id} className="border rounded p-2">
              <div className="font-medium">{l.action}</div>
              <div className="text-muted-foreground">{l.created_at}</div>
              <div>{l?.changes?.message || JSON.stringify(l?.changes || {})}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
