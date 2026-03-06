import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminUsersApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';

export default function AdminUsers() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ['admin-users'], queryFn: adminUsersApi.list });

  const mutate = useMutation({
    mutationFn: async ({ userId, action, role }: { userId: string; action: 'activate' | 'deactivate' | 'role'; role?: 'admin' | 'agent' | 'user' }) => {
      if (action === 'activate') return adminUsersApi.activate(userId);
      if (action === 'deactivate') return adminUsersApi.deactivate(userId);
      return adminUsersApi.setRole(userId, role!);
    },
    onSuccess: () => {
      toast.success('Zapisano');
      qc.invalidateQueries({ queryKey: ['admin-users'] });
    },
    onError: (e: any) => toast.error(e.message || 'Błąd'),
  });

  const users = data?.users || [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Admin • Użytkownicy</h1>
      <Card>
        <CardHeader><CardTitle>Zarządzanie użytkownikami</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {users.map((u: any) => (
            <div key={u.id} className="border rounded p-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-medium">{u.name || u.email}</div>
                <div className="text-xs text-muted-foreground">{u.email}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline">{u.role}</Badge>
                <Badge variant={u.is_active ? 'default' : 'secondary'}>{u.is_active ? 'AKTYWNY' : 'NIEAKTYWNY'}</Badge>
                <Select onValueChange={(role: any) => mutate.mutate({ userId: u.id, action: 'role', role })}>
                  <SelectTrigger className="w-32"><SelectValue placeholder="Rola" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">user</SelectItem>
                    <SelectItem value="agent">agent</SelectItem>
                    <SelectItem value="admin">admin</SelectItem>
                  </SelectContent>
                </Select>
                {u.is_active ? (
                  <Button variant="destructive" size="sm" onClick={() => mutate.mutate({ userId: u.id, action: 'deactivate' })}>Dezaktywuj</Button>
                ) : (
                  <Button size="sm" onClick={() => mutate.mutate({ userId: u.id, action: 'activate' })}>Aktywuj</Button>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
