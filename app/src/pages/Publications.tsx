import { useQuery } from '@tanstack/react-query';
import { propertiesApi, otodomApi } from '@/lib/api';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export default function Publications() {
  const { data: listings = [], isLoading } = useQuery({
    queryKey: ['properties-publications'],
    queryFn: () => propertiesApi.getAll(),
  });

  const { data: states = {} } = useQuery({
    queryKey: ['otodom-publications-state', listings.map((l) => l.id).join(',')],
    queryFn: async () => {
      const out: Record<string, any> = {};
      for (const l of listings.slice(0, 80)) {
        try {
          out[l.id] = await otodomApi.getPublication(l.id);
        } catch {
          out[l.id] = { publication_status: 'not_available' };
        }
      }
      return out;
    },
    enabled: listings.length > 0,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Publikacje Otodom</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Oferty i status publikacji</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p>Ładowanie...</p>
          ) : (
            <div className="space-y-2">
              {listings.map((l) => {
                const pub = states[l.id] || { publication_status: 'not_published' };
                return (
                  <div key={l.id} className="flex items-center justify-between gap-3 rounded border p-3">
                    <div>
                      <div className="font-medium">{l.title}</div>
                      <div className="text-xs text-muted-foreground">{l.city} • {l.price?.toLocaleString('pl-PL')} PLN</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{pub.publication_status || 'not_published'}</Badge>
                      <Button asChild variant="outline" size="sm"><Link to={`/properties/${l.id}`}>Szczegóły</Link></Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
