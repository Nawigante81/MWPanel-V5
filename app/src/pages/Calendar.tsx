import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  Clock,
  MapPin,
  User,
  Home,
  Phone,
  Calendar as CalendarIcon,
  List,
  CalendarDays,
  Pencil,
  Trash2,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { calendarApi, type CalendarEventApi } from '@/lib/api';

type CalendarEvent = {
  id: string;
  title: string;
  type: 'viewing' | 'meeting' | 'call' | 'task';
  startAt: string;
  endAt: string;
  date: string;
  startTime: string;
  endTime: string;
  location?: string;
  contactName?: string;
  listingTitle?: string;
  description?: string;
  status: 'scheduled' | 'completed' | 'cancelled';
  reminderMinutes?: number;
};

const eventTypeConfig = {
  viewing: { label: 'Oglądanie', color: 'blue', icon: Home },
  meeting: { label: 'Spotkanie', color: 'green', icon: User },
  call: { label: 'Telefon', color: 'amber', icon: Phone },
  task: { label: 'Inne', color: 'purple', icon: CalendarIcon },
};

const statusConfig = {
  scheduled: { label: 'Planowane', variant: 'default' as const },
  completed: { label: 'Wykonane', variant: 'secondary' as const },
  cancelled: { label: 'Anulowane', variant: 'destructive' as const },
};

const toDate = (d: Date) => d.toISOString().slice(0, 10);
const toTime = (iso: string) => new Date(iso).toISOString().slice(11, 16);

function mapApiEvent(e: CalendarEventApi): CalendarEvent {
  const eventType = e.event_type === 'presentation' ? 'viewing' : e.event_type === 'other' ? 'task' : (e.event_type as any);
  return {
    id: e.id,
    title: e.title,
    type: ['viewing', 'meeting', 'call', 'task'].includes(eventType) ? eventType : 'task',
    startAt: e.start_at,
    endAt: e.end_at,
    date: e.start_at.slice(0, 10),
    startTime: toTime(e.start_at),
    endTime: toTime(e.end_at),
    location: e.location,
    contactName: e.contact_name,
    listingTitle: e.listing_title,
    description: e.description,
    status: (e.status || 'scheduled') as CalendarEvent['status'],
    reminderMinutes: e.reminder_minutes,
  };
}

function DayColumn({
  date,
  events,
  onEventClick,
  onSlotClick,
}: {
  date: Date;
  events: CalendarEvent[];
  onEventClick: (e: CalendarEvent) => void;
  onSlotClick: (date: string, hour: number) => void;
}) {
  const isToday = toDate(date) === toDate(new Date());
  const hours = Array.from({ length: 12 }, (_, i) => i + 8);
  const dateStr = toDate(date);

  return (
    <div className="min-w-0 border-r last:border-r-0">
      <div className={cn('p-2 border-b text-center sticky top-0 bg-background z-10', isToday && 'bg-primary/5')}>
        <div className="text-xs uppercase text-muted-foreground">{date.toLocaleDateString('pl-PL', { weekday: 'short' })}</div>
        <div className={cn('text-lg font-bold', isToday && 'text-primary')}>{date.getDate()}</div>
      </div>

      <div>
        {hours.map((h) => {
          const hh = `${String(h).padStart(2, '0')}:`;
          const slotEvents = events.filter((e) => e.date === dateStr && e.startTime.startsWith(hh));
          return (
            <button
              key={h}
              type="button"
              onClick={() => onSlotClick(dateStr, h)}
              className="w-full text-left border-b p-1.5 hover:bg-accent/50 min-h-[58px]"
            >
              <div className="text-[10px] text-muted-foreground mb-1">{String(h).padStart(2, '0')}:00</div>
              <div className="space-y-1">
                {slotEvents.map((e) => (
                  <div
                    key={e.id}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      onEventClick(e);
                    }}
                    className="rounded bg-primary/10 px-1.5 py-1 text-[11px] truncate"
                  >
                    {e.startTime} {e.title}
                  </div>
                ))}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function Calendar() {
  const queryClient = useQueryClient();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<'week' | 'list'>('week');
  const [search, setSearch] = useState('');

  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [slotDate, setSlotDate] = useState<string>('');
  const [slotHour, setSlotHour] = useState<number>(10);

  const startOfWeek = useMemo(() => {
    const d = new Date(currentDate);
    const day = d.getDay() || 7;
    d.setDate(d.getDate() - day + 1);
    d.setHours(0, 0, 0, 0);
    return d;
  }, [currentDate]);

  const endOfWeek = useMemo(() => {
    const d = new Date(startOfWeek);
    d.setDate(d.getDate() + 7);
    return d;
  }, [startOfWeek]);

  const weekDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    return d;
  });

  const { data: rawEvents = [], isLoading } = useQuery({
    queryKey: ['calendar-events', toDate(startOfWeek), toDate(endOfWeek)],
    queryFn: () => calendarApi.getRange({ from: startOfWeek.toISOString(), to: endOfWeek.toISOString() }),
    refetchInterval: 30000,
  });

  const events = rawEvents.map(mapApiEvent);
  const filtered = events.filter((e) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return [e.title, e.contactName, e.location, e.listingTitle].filter(Boolean).join(' ').toLowerCase().includes(q);
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<CalendarEventApi> }) => calendarApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-payload'] });
      setDetailsOpen(false);
      setIsEditing(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => calendarApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] });
      setDetailsOpen(false);
      setIsEditing(false);
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: Partial<CalendarEventApi>) => calendarApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] });
      setCreateOpen(false);
    },
  });

  const openEvent = (e: CalendarEvent) => {
    setSelectedEvent(e);
    setIsEditing(false);
    setDetailsOpen(true);
  };

  const openSlot = (date: string, hour: number) => {
    setSlotDate(date);
    setSlotHour(hour);
    setCreateOpen(true);
  };

  const navigateWeek = (dir: 'prev' | 'next') => {
    const d = new Date(currentDate);
    d.setDate(d.getDate() + (dir === 'next' ? 7 : -7));
    setCurrentDate(d);
  };

  const [editForm, setEditForm] = useState<any>({});

  const onStartEdit = () => {
    if (!selectedEvent) return;
    setEditForm({
      title: selectedEvent.title,
      event_type: selectedEvent.type,
      start_at: selectedEvent.startAt,
      end_at: selectedEvent.endAt,
      status: selectedEvent.status,
      contact_name: selectedEvent.contactName || '',
      listing_title: selectedEvent.listingTitle || '',
      location: selectedEvent.location || '',
      description: selectedEvent.description || '',
      reminder_minutes: selectedEvent.reminderMinutes || 15,
    });
    setIsEditing(true);
  };

  const [createForm, setCreateForm] = useState<any>({
    title: '',
    event_type: 'meeting',
    status: 'scheduled',
    contact_name: '',
    listing_title: '',
    location: '',
    description: '',
    reminder_minutes: 15,
  });

  const saveCreate = () => {
    const startAt = new Date(`${slotDate}T${String(slotHour).padStart(2, '0')}:00:00`);
    const endAt = new Date(startAt.getTime() + 60 * 60 * 1000);
    createMutation.mutate({
      ...createForm,
      start_at: startAt.toISOString(),
      end_at: endAt.toISOString(),
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Kalendarz</h1>
          <p className="text-muted-foreground">Kliknij wydarzenie, aby zobaczyć szczegóły i edytować.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center bg-muted rounded-lg p-1">
            <Button variant={view === 'week' ? 'secondary' : 'ghost'} size="sm" onClick={() => setView('week')}><CalendarDays className="w-4 h-4 mr-1" />Tydzień</Button>
            <Button variant={view === 'list' ? 'secondary' : 'ghost'} size="sm" onClick={() => setView('list')}><List className="w-4 h-4 mr-1" />Lista</Button>
          </div>
          <Button variant="outline" onClick={() => navigateWeek('prev')}><ChevronLeft className="w-4 h-4" /></Button>
          <span className="text-sm font-medium min-w-[88px] sm:min-w-[170px] text-center">
            {weekDays[0].toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })} - {weekDays[6].toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })}
          </span>
          <Button variant="outline" onClick={() => navigateWeek('next')}><ChevronRight className="w-4 h-4" /></Button>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button><Plus className="w-4 h-4 mr-2" />Nowe</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Nowe wydarzenie</DialogTitle></DialogHeader>
              <div className="space-y-3">
                <Input placeholder="Tytuł" value={createForm.title} onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })} />
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <Select value={createForm.event_type} onValueChange={(v) => setCreateForm({ ...createForm, event_type: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="meeting">Spotkanie</SelectItem>
                      <SelectItem value="call">Telefon</SelectItem>
                      <SelectItem value="viewing">Prezentacja/Oglądanie</SelectItem>
                      <SelectItem value="other">Inne</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input type="date" value={slotDate} onChange={(e) => setSlotDate(e.target.value)} />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <Input type="number" min={0} max={23} value={slotHour} onChange={(e) => setSlotHour(Number(e.target.value))} />
                  <Input placeholder="Lokalizacja" value={createForm.location} onChange={(e) => setCreateForm({ ...createForm, location: e.target.value })} />
                </div>
                <Input placeholder="Kontakt" value={createForm.contact_name} onChange={(e) => setCreateForm({ ...createForm, contact_name: e.target.value })} />
                <Input placeholder="Powiązana oferta" value={createForm.listing_title} onChange={(e) => setCreateForm({ ...createForm, listing_title: e.target.value })} />
                <Textarea placeholder="Opis / notatki" value={createForm.description} onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })} />
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setCreateOpen(false)}>Anuluj</Button>
                  <Button onClick={saveCreate} disabled={!createForm.title || !slotDate}>Zapisz</Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Input placeholder="Szukaj wydarzeń..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />
      </div>

      {isLoading ? (
        <Card><CardContent className="p-6 text-sm text-muted-foreground">Ładowanie kalendarza...</CardContent></Card>
      ) : view === 'week' ? (
        <Card>
          <CardContent className="p-0 overflow-x-auto">
            <div className="grid grid-cols-1 md:grid-cols-7 min-w-[900px] md:min-w-0">
              {weekDays.map((d) => (
                <DayColumn key={d.toISOString()} date={d} events={filtered} onEventClick={openEvent} onSlotClick={openSlot} />
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader><CardTitle>Wydarzenia</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {filtered.map((e) => (
              <button key={e.id} type="button" onClick={() => openEvent(e)} className="w-full text-left rounded-lg border p-3 hover:bg-accent/50">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium">{e.title}</div>
                  <Badge variant={statusConfig[e.status].variant}>{statusConfig[e.status].label}</Badge>
                </div>
                <div className="text-sm text-muted-foreground mt-1">{new Date(e.startAt).toLocaleString('pl-PL')} - {new Date(e.endAt).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })}</div>
              </button>
            ))}
            {!filtered.length && <div className="text-sm text-muted-foreground">Brak wydarzeń.</div>}
          </CardContent>
        </Card>
      )}

      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Szczegóły wydarzenia</DialogTitle></DialogHeader>
          {!selectedEvent ? null : !isEditing ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-xl font-semibold">{selectedEvent.title}</h3>
                <Badge variant={statusConfig[selectedEvent.status].variant}>{statusConfig[selectedEvent.status].label}</Badge>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                <div className="flex items-center gap-2"><Clock className="w-4 h-4" />{new Date(selectedEvent.startAt).toLocaleString('pl-PL')} - {new Date(selectedEvent.endAt).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })}</div>
                <div className="flex items-center gap-2"><CalendarIcon className="w-4 h-4" />{eventTypeConfig[selectedEvent.type].label}</div>
                <div className="flex items-center gap-2"><User className="w-4 h-4" />{selectedEvent.contactName || '—'}</div>
                <div className="flex items-center gap-2"><Home className="w-4 h-4" />{selectedEvent.listingTitle || '—'}</div>
                <div className="flex items-center gap-2 sm:col-span-2"><MapPin className="w-4 h-4" />{selectedEvent.location || '—'}</div>
              </div>
              <div className="text-sm"><span className="font-medium">Opis:</span> {selectedEvent.description || '—'}</div>
              <div className="text-sm"><span className="font-medium">Przypomnienie:</span> {selectedEvent.reminderMinutes ?? 15} min</div>
              <div className="flex flex-wrap gap-2 pt-2">
                <Button variant="outline" onClick={onStartEdit}><Pencil className="w-4 h-4 mr-1" />Edytuj</Button>
                <Button variant="outline" onClick={() => updateMutation.mutate({ id: selectedEvent.id, payload: { status: 'completed' } })}>Oznacz wykonane</Button>
                <Button variant="destructive" onClick={() => deleteMutation.mutate(selectedEvent.id)}><Trash2 className="w-4 h-4 mr-1" />Usuń</Button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <Input value={editForm.title || ''} onChange={(e) => setEditForm({ ...editForm, title: e.target.value })} />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Input type="datetime-local" value={(editForm.start_at || '').slice(0, 16)} onChange={(e) => setEditForm({ ...editForm, start_at: new Date(e.target.value).toISOString() })} />
                <Input type="datetime-local" value={(editForm.end_at || '').slice(0, 16)} onChange={(e) => setEditForm({ ...editForm, end_at: new Date(e.target.value).toISOString() })} />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <Select value={editForm.event_type} onValueChange={(v) => setEditForm({ ...editForm, event_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="meeting">Spotkanie</SelectItem>
                    <SelectItem value="call">Telefon</SelectItem>
                    <SelectItem value="viewing">Prezentacja/Oglądanie</SelectItem>
                    <SelectItem value="other">Inne</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={editForm.status} onValueChange={(v) => setEditForm({ ...editForm, status: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="scheduled">Planowane</SelectItem>
                    <SelectItem value="completed">Wykonane</SelectItem>
                    <SelectItem value="cancelled">Anulowane</SelectItem>
                  </SelectContent>
                </Select>
                <Input type="number" min={0} value={editForm.reminder_minutes || 15} onChange={(e) => setEditForm({ ...editForm, reminder_minutes: Number(e.target.value) })} />
              </div>
              <Input placeholder="Kontakt" value={editForm.contact_name || ''} onChange={(e) => setEditForm({ ...editForm, contact_name: e.target.value })} />
              <Input placeholder="Powiązana oferta" value={editForm.listing_title || ''} onChange={(e) => setEditForm({ ...editForm, listing_title: e.target.value })} />
              <Input placeholder="Lokalizacja" value={editForm.location || ''} onChange={(e) => setEditForm({ ...editForm, location: e.target.value })} />
              <Textarea placeholder="Opis" value={editForm.description || ''} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} />
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setIsEditing(false)}>Anuluj</Button>
                <Button onClick={() => selectedEvent && updateMutation.mutate({ id: selectedEvent.id, payload: editForm })}>Zapisz</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
