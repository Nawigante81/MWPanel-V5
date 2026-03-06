import { useQuery } from '@tanstack/react-query';
import { auditLogsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';

function formatDate(value?: string) {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('pl-PL');
}

export default function AuditLogs() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => auditLogsApi.getAll(100),
  });

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Nie udało się pobrać logów audytowych.</AlertDescription>
      </Alert>
    );
  }

  const items = data?.items || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Audit log</h1>
        <p className="text-muted-foreground">Podgląd zmian w systemie (readonly).</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ostatnie wpisy ({data?.total ?? 0})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-20 w-full" />)}
            </div>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Brak wpisów audit log.</p>
          ) : (
            items.map((log: any) => (
              <div key={log.id} className="rounded-xl border p-4 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{log.entity || 'entity'}</Badge>
                  <Badge>{log.action || 'action'}</Badge>
                  <span className="text-xs text-muted-foreground">ID: {log.entity_id || '-'}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  {formatDate(log.created_at || log.timestamp)} • actor: {log.actor || 'system'}
                </div>
                <pre className="text-xs bg-muted rounded-md p-2 overflow-auto">{JSON.stringify(log.changes || {}, null, 2)}</pre>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
