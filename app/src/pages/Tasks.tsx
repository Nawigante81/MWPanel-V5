import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tasksApi, followupsApi } from '@/lib/api';
import type { Task } from '@/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogClose,
  DialogDescription,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Plus,
  CheckSquare,
  AlertCircle,
  Calendar,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Circle,
  Trash2,
  Edit,
  Flag,
  Timer,
  Target,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const statusLabels: Record<string, string> = {
  pending: 'Oczekujące',
  in_progress: 'W trakcie',
  completed: 'Ukończone',
  cancelled: 'Anulowane',
};

const followupStatusLabels: Record<string, string> = {
  pending: 'oczekujące',
  in_progress: 'w trakcie',
  completed: 'ukończone',
  cancelled: 'anulowane',
};

const priorityConfig: Record<string, { label: string; class: string; icon: React.ElementType }> = {
  low: { 
    label: 'Niski', 
    class: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
    icon: Flag
  },
  medium: { 
    label: 'Średni', 
    class: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    icon: Flag
  },
  high: { 
    label: 'Wysoki', 
    class: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20',
    icon: AlertTriangle
  },
  urgent: { 
    label: 'Pilny', 
    class: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
    icon: AlertTriangle
  },
};

function TaskForm({
  task,
  onSubmit,
  onCancel,
}: {
  task?: Task;
  onSubmit: (data: Partial<Task>) => void;
  onCancel: () => void;
}) {
  const [formData, setFormData] = useState<Partial<Task>>({
    title: task?.title || '',
    description: task?.description || '',
    priority: task?.priority || 'medium',
    due_date: task?.due_date || '',
    status: task?.status || 'pending',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="title">Tytuł *</Label>
        <Input
          id="title"
          value={formData.title}
          onChange={(e) => setFormData({ ...formData, title: e.target.value })}
          placeholder="Np. Skontaktować się z klientem"
          required
          className="rounded-xl"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Opis</Label>
        <Textarea
          id="description"
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          placeholder="Szczegóły zadania..."
          className="rounded-xl min-h-[80px]"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="priority">Priorytet</Label>
          <Select
            value={formData.priority}
            onValueChange={(value) => setFormData({ ...formData, priority: value as Task['priority'] })}
          >
            <SelectTrigger className="rounded-xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Niski</SelectItem>
              <SelectItem value="medium">Średni</SelectItem>
              <SelectItem value="high">Wysoki</SelectItem>
              <SelectItem value="urgent">Pilny</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="due_date">Termin</Label>
          <Input
            id="due_date"
            type="date"
            value={formData.due_date?.split('T')[0] || ''}
            onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
            className="rounded-xl"
          />
        </div>
      </div>

      {task && (
        <div className="space-y-2">
          <Label htmlFor="status">Status</Label>
          <Select
            value={formData.status}
            onValueChange={(value) => setFormData({ ...formData, status: value as Task['status'] })}
          >
            <SelectTrigger className="rounded-xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pending">Oczekujące</SelectItem>
              <SelectItem value="in_progress">W trakcie</SelectItem>
              <SelectItem value="completed">Ukończone</SelectItem>
              <SelectItem value="cancelled">Anulowane</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline" onClick={onCancel} className="rounded-xl">
            Anuluj
          </Button>
        </DialogClose>
        <Button type="submit" className="rounded-xl">
          {task ? 'Zapisz zmiany' : 'Dodaj zadanie'}
        </Button>
      </DialogFooter>
    </form>
  );
}

function TaskCard({
  task,
  onStatusChange,
  onEdit,
  onDelete,
}: {
  task: Task;
  onStatusChange: (id: string, status: Task['status']) => void;
  onEdit: (task: Task) => void;
  onDelete: (id: string) => void;
}) {
  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== 'completed';
  const isCompleted = task.status === 'completed';
  const isInProgress = task.status === 'in_progress';
  const PriorityIcon = priorityConfig[task.priority].icon;

  return (
    <Card className={cn(
      'card-hover group transition-all duration-200',
      isCompleted && 'opacity-60',
      isOverdue && 'border-rose-500/50 bg-rose-500/5'
    )}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <Checkbox
            checked={isCompleted}
            onCheckedChange={(checked) =>
              onStatusChange(task.id, checked ? 'completed' : 'pending')
            }
            className={cn(
              'mt-1 rounded-full border-2 h-5 w-5',
              isCompleted && 'bg-primary border-primary'
            )}
          />

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <h3 className={cn(
                  'font-semibold transition-all',
                  isCompleted && 'line-through text-muted-foreground'
                )}>
                  {task.title}
                </h3>
                {task.description && (
                  <p className={cn(
                    'text-sm text-muted-foreground mt-1',
                    isCompleted && 'line-through'
                  )}>
                    {task.description}
                  </p>
                )}
              </div>
              
              <div className="flex items-center gap-1">
                <Badge variant="secondary" className={cn('text-[10px]', priorityConfig[task.priority].class)}>
                  <PriorityIcon className="h-3 w-3 mr-1" />
                  {priorityConfig[task.priority].label}
                </Badge>
                
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => onEdit(task)}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive"
                  onClick={() => onDelete(task.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="flex items-center gap-4 mt-3 text-xs">
              {task.due_date && (
                <span className={cn(
                  'flex items-center gap-1.5 px-2 py-1 rounded-lg',
                  isOverdue 
                    ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400' 
                    : 'bg-muted text-muted-foreground'
                )}>
                  <Calendar className="h-3.5 w-3.5" />
                  {new Date(task.due_date).toLocaleDateString('pl-PL')}
                  {isOverdue && <span className="font-medium">(przeterminowane)</span>}
                </span>
              )}
              
              <span className={cn(
                'flex items-center gap-1.5 px-2 py-1 rounded-lg',
                isCompleted && 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
                isInProgress && 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
                !isCompleted && !isInProgress && 'bg-muted text-muted-foreground'
              )}>
                <Clock className="h-3.5 w-3.5" />
                {statusLabels[task.status]}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function TasksSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4].map((i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <Skeleton className="h-5 w-5 mt-1 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function Tasks() {
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [filter, setFilter] = useState<'all' | 'pending' | 'in_progress' | 'completed'>('all');
  const queryClient = useQueryClient();

  const { data: tasks, isLoading, error } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => tasksApi.getAll(),
  });

  const { data: followups } = useQuery({
    queryKey: ['followups'],
    queryFn: followupsApi.getAll,
  });

  const createMutation = useMutation({
    mutationFn: tasksApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      toast.success('Zadanie dodane');
      setIsAddDialogOpen(false);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd dodawania zadania');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Task> }) =>
      tasksApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      toast.success('Zadanie zaktualizowane');
      setEditingTask(null);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd aktualizacji zadania');
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: Task['status'] }) =>
      tasksApi.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      toast.success('Status zaktualizowany');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd aktualizacji statusu');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: tasksApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      toast.success('Zadanie usunięte');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd usuwania zadania');
    },
  });

  const remindMutation = useMutation({
    mutationFn: ({ taskId, reminderAt }: { taskId: string; reminderAt: string }) =>
      followupsApi.remind(taskId, reminderAt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['followups'] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      toast.success('Ustawiono przypomnienie follow-up');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd ustawiania przypomnienia');
    },
  });

  const filteredTasks = tasks?.filter((task) => {
    if (filter === 'pending') return task.status === 'pending';
    if (filter === 'in_progress') return task.status === 'in_progress';
    if (filter === 'completed') return task.status === 'completed';
    return true;
  });

  const stats = {
    total: tasks?.length || 0,
    pending: tasks?.filter((t) => t.status === 'pending').length || 0,
    inProgress: tasks?.filter((t) => t.status === 'in_progress').length || 0,
    completed: tasks?.filter((t) => t.status === 'completed').length || 0,
    overdue: tasks?.filter((t) => 
      t.due_date && new Date(t.due_date) < new Date() && t.status !== 'completed'
    ).length || 0,
  };

  const completionRate = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0;

  const handleCreate = (data: Partial<Task>) => {
    createMutation.mutate(data);
  };

  const handleUpdate = (data: Partial<Task>) => {
    if (editingTask) {
      updateMutation.mutate({ id: editingTask.id, data });
    }
  };

  const handleStatusChange = (id: string, status: Task['status']) => {
    updateStatusMutation.mutate({ id, status });
  };

  const handleDelete = (id: string) => {
    if (confirm('Czy na pewno chcesz usunąć to zadanie?')) {
      deleteMutation.mutate(id);
    }
  };

  if (error) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Zadania</h1>
            <p className="text-muted-foreground">Zarządzaj zadaniami i terminarzem</p>
          </div>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Nie udało się pobrać zadań. Spróbuj odświeżyć stronę.
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
          <h1 className="text-3xl font-bold tracking-tight">Zadania</h1>
          <p className="text-muted-foreground">Zarządzaj zadaniami i terminarzem</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-xl">
              <Plus className="mr-2 h-4 w-4" />
              Nowe zadanie
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Dodaj nowe zadanie</DialogTitle>
              <DialogDescription>
                Utwórz nowe zadanie do wykonania.
              </DialogDescription>
            </DialogHeader>
            <TaskForm
              onSubmit={handleCreate}
              onCancel={() => setIsAddDialogOpen(false)}
            />
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="card-hover bg-gradient-to-br from-blue-500/10 to-blue-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Wszystkie</p>
            <p className="text-2xl font-bold">{stats.total}</p>
          </CardContent>
        </Card>
        <Card className="card-hover bg-gradient-to-br from-amber-500/10 to-amber-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Oczekujące</p>
            <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">{stats.pending}</p>
          </CardContent>
        </Card>
        <Card className="card-hover bg-gradient-to-br from-emerald-500/10 to-emerald-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Ukończone</p>
            <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{stats.completed}</p>
          </CardContent>
        </Card>
        <Card className={cn(
          'card-hover',
          stats.overdue > 0 
            ? 'bg-gradient-to-br from-rose-500/10 to-rose-600/5' 
            : 'bg-gradient-to-br from-gray-500/10 to-gray-600/5'
        )}>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Przeterminowane</p>
            <p className={cn(
              'text-2xl font-bold',
              stats.overdue > 0 ? 'text-rose-600 dark:text-rose-400' : ''
            )}>
              {stats.overdue}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Progress Card */}
      <Card className="card-hover">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-primary" />
              <span className="font-medium">Postęp zadań</span>
            </div>
            <span className="text-sm font-semibold">{completionRate}%</span>
          </div>
          <Progress value={completionRate} className="h-2" />
          <p className="text-xs text-muted-foreground mt-2">
            {stats.completed} z {stats.total} zadań ukończonych
          </p>
        </CardContent>
      </Card>

      {/* Follow-up Workflow */}
      <Card className="card-hover">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-primary" />
              <span className="font-medium">Follow-up i przypomnienia</span>
            </div>
            <Badge variant="secondary">{followups?.length || 0}</Badge>
          </div>
          {!followups?.length ? (
            <p className="text-sm text-muted-foreground">Brak aktywnych follow-upów.</p>
          ) : (
            <div className="space-y-2">
              {followups.slice(0, 5).map((f: any) => (
                <div key={f.id} className="flex items-center justify-between rounded-lg border p-2">
                  <div>
                    <div className="text-sm font-medium">{f.title}</div>
                    <div className="text-xs text-muted-foreground">status: {followupStatusLabels[f.status] || f.status}</div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-lg"
                    disabled={remindMutation.isPending}
                    onClick={() => {
                      const d = new Date();
                      d.setDate(d.getDate() + 1);
                      remindMutation.mutate({ taskId: f.id, reminderAt: d.toISOString() });
                    }}
                  >
                    {remindMutation.isPending ? 'Ustawiam...' : 'Przypomnij +1d'}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        <Button
          variant={filter === 'all' ? 'default' : 'outline'}
          onClick={() => setFilter('all')}
          className="rounded-xl"
          size="sm"
        >
          Wszystkie ({stats.total})
        </Button>
        <Button
          variant={filter === 'pending' ? 'default' : 'outline'}
          onClick={() => setFilter('pending')}
          className="rounded-xl"
          size="sm"
        >
          <Circle className="mr-2 h-4 w-4" />
          Oczekujące ({stats.pending})
        </Button>
        <Button
          variant={filter === 'in_progress' ? 'default' : 'outline'}
          onClick={() => setFilter('in_progress')}
          className="rounded-xl"
          size="sm"
        >
          <Timer className="mr-2 h-4 w-4" />
          W trakcie ({stats.inProgress})
        </Button>
        <Button
          variant={filter === 'completed' ? 'default' : 'outline'}
          onClick={() => setFilter('completed')}
          className="rounded-xl"
          size="sm"
        >
          <CheckCircle2 className="mr-2 h-4 w-4" />
          Ukończone ({stats.completed})
        </Button>
      </div>

      {/* Tasks List */}
      {isLoading ? (
        <TasksSkeleton />
      ) : filteredTasks?.length === 0 ? (
        <Card className="card-hover">
          <CardContent className="p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
              <CheckSquare className="h-10 w-10 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Brak zadań</h3>
            <p className="text-muted-foreground mb-4 max-w-md mx-auto">
              {filter === 'completed'
                ? 'Nie masz jeszcze ukończonych zadań'
                : filter === 'in_progress'
                ? 'Nie masz zadań w trakcie realizacji'
                : 'Nie masz żadnych zadań do wykonania. Dodaj pierwsze zadanie, aby rozpocząć.'}
            </p>
            <Button onClick={() => setIsAddDialogOpen(true)} className="rounded-xl">
              <Plus className="mr-2 h-4 w-4" />
              Dodaj zadanie
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredTasks?.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onStatusChange={handleStatusChange}
              onEdit={setEditingTask}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {/* Edit Dialog */}
      <Dialog open={!!editingTask} onOpenChange={() => setEditingTask(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edytuj zadanie</DialogTitle>
            <DialogDescription>
              Zmień szczegóły zadania.
            </DialogDescription>
          </DialogHeader>
          {editingTask && (
            <TaskForm
              task={editingTask}
              onSubmit={handleUpdate}
              onCancel={() => setEditingTask(null)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
