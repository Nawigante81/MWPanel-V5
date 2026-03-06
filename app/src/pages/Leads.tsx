import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { leadsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

type LeadStatus = 'new' | 'contacted' | 'qualified' | 'won' | 'lost';

const STATUS_OPTIONS: LeadStatus[] = ['new', 'contacted', 'qualified', 'won', 'lost'];

const STATUS_LABELS: Record<LeadStatus, string> = {
  new: 'Nowy',
  contacted: 'Skontaktowany',
  qualified: 'Zakwalifikowany',
  won: 'Wygrany',
  lost: 'Przegrany',
};

const STATUS_BADGE: Record<LeadStatus, string> = {
  new: 'bg-slate-500/10 text-slate-700 dark:text-slate-300',
  contacted: 'bg-blue-500/10 text-blue-700 dark:text-blue-300',
  qualified: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
  won: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  lost: 'bg-rose-500/10 text-rose-700 dark:text-rose-300',
};

export default function Leads() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [scoreFilter, setScoreFilter] = useState<string>('0');

  const { data, isLoading, error } = useQuery({
    queryKey: ['leads', statusFilter],
    queryFn: () => leadsApi.getAll(statusFilter === 'all' ? undefined : { status: statusFilter }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, any> }) => leadsApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      toast.success('Lead zaktualizowany');
    },
    onError: (e: any) => toast.error(e.message || 'Nie udało się zaktualizować leada'),
  });

  const leads = useMemo(() => {
    const min = Number(scoreFilter || '0');
    return (data || []).filter((lead: any) => Number(lead.score || 0) >= min);
  }, [data, scoreFilter]);

  const avgScore = leads.length
    ? Math.round(leads.reduce((acc: number, lead: any) => acc + Number(lead.score || 0), 0) / leads.length)
    : 0;

  const funnel = STATUS_OPTIONS.reduce((acc, status) => {
    acc[status] = leads.filter((lead: any) => lead.status === status).length;
    return acc;
  }, {} as Record<LeadStatus, number>);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Nie udało się pobrać leadów.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Leady</h1>
        <p className="text-muted-foreground">Lejek sprzedaży i scoring leadów.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Łącznie leadów</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{isLoading ? <Skeleton className="h-8 w-20" /> : leads.length}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Średni score</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-8 w-20" /> : <div className="text-2xl font-semibold">{avgScore}/100</div>}
            <Progress value={avgScore} className="mt-2 h-2" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Filtry</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col sm:flex-row gap-2">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Wszystkie</SelectItem>
                {STATUS_OPTIONS.map((status) => (
                  <SelectItem key={status} value={status}>{STATUS_LABELS[status]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="number"
              min={0}
              max={100}
              value={scoreFilter}
              onChange={(e) => setScoreFilter(e.target.value)}
              placeholder="Min. score"
              className="w-full sm:w-36"
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lejek leadów</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-5">
            {STATUS_OPTIONS.map((status) => (
              <div key={status} className="rounded-xl border p-3">
                <div className="text-xs text-muted-foreground">{STATUS_LABELS[status]}</div>
                <div className="text-2xl font-semibold">{isLoading ? '...' : funnel[status]}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lista leadów</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}
            </div>
          ) : leads.length === 0 ? (
            <p className="text-sm text-muted-foreground">Brak leadów dla aktualnych filtrów.</p>
          ) : (
            leads.map((lead: any) => (
              <div key={lead.id} className="rounded-xl border p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1 min-w-0">
                  <div className="font-medium text-safe-wrap">{lead.name || lead.email || `Lead ${lead.id.slice(0, 8)}`}</div>
                  <div className="text-xs text-muted-foreground">Źródło: {lead.source || 'nieznane'}</div>
                  <Badge variant="secondary" className={STATUS_BADGE[(lead.status as LeadStatus) || 'new']}>
                    {STATUS_LABELS[(lead.status as LeadStatus) || 'new']}
                  </Badge>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center gap-2 w-full sm:w-auto">
                  <div className="w-full sm:w-32">
                    <div className="text-xs text-muted-foreground mb-1">Score: {lead.score || 0}</div>
                    <Progress value={Number(lead.score || 0)} className="h-2" />
                  </div>
                  <Select
                    defaultValue={(lead.status as LeadStatus) || 'new'}
                    onValueChange={(status) => updateMutation.mutate({ id: lead.id, payload: { status } })}
                  >
                    <SelectTrigger className="w-full sm:w-[170px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((status) => (
                        <SelectItem key={status} value={status}>{STATUS_LABELS[status]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    variant="outline"
                    className="w-full sm:w-auto"
                    onClick={() => updateMutation.mutate({ id: lead.id, payload: { score: Math.min(100, Number(lead.score || 0) + 10) } })}
                  >
                    +10 score
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
