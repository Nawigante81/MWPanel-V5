import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { contactsApi, contactTimelineApi } from '@/lib/api';
import type { Contact } from '@/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
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
  Search,
  Plus,
  MoreVertical,
  Phone,
  Mail,
  User,
  AlertCircle,
  Edit,
  Trash2,
  Users,
  Building2,
  MessageSquare,
  Filter,
  Briefcase,
  History,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const typeLabels: Record<string, string> = {
  client: 'Klient',
  owner: 'Właściciel',
  partner: 'Partner',
  other: 'Inny',
};

const typeConfig: Record<string, { label: string; class: string; icon: React.ElementType }> = {
  client: { 
    label: 'Klient', 
    class: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
    icon: User
  },
  owner: { 
    label: 'Właściciel', 
    class: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    icon: Building2
  },
  partner: { 
    label: 'Partner', 
    class: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
    icon: Briefcase
  },
  other: { 
    label: 'Inny', 
    class: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20',
    icon: User
  },
};

function ContactForm({
  contact,
  onSubmit,
  onCancel,
}: {
  contact?: Contact;
  onSubmit: (data: Partial<Contact>) => void;
  onCancel: () => void;
}) {
  const [formData, setFormData] = useState<Partial<Contact>>({
    name: contact?.name || '',
    phone: contact?.phone || '',
    email: contact?.email || '',
    type: contact?.type || 'client',
    notes: contact?.notes || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">Imię i nazwisko *</Label>
        <Input
          id="name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="Jan Kowalski"
          required
          className="rounded-xl"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="phone">Telefon</Label>
          <Input
            id="phone"
            value={formData.phone}
            onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
            placeholder="+48 123 456 789"
            className="rounded-xl"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            placeholder="jan@example.com"
            className="rounded-xl"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="type">Typ kontaktu</Label>
        <Select
          value={formData.type}
          onValueChange={(value) => setFormData({ ...formData, type: value as Contact['type'] })}
        >
          <SelectTrigger className="rounded-xl">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="client">
              <div className="flex items-center gap-2">
                <User className="h-4 w-4" />
                Klient
              </div>
            </SelectItem>
            <SelectItem value="owner">
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                Właściciel
              </div>
            </SelectItem>
            <SelectItem value="partner">
              <div className="flex items-center gap-2">
                <Briefcase className="h-4 w-4" />
                Partner
              </div>
            </SelectItem>
            <SelectItem value="other">
              <div className="flex items-center gap-2">
                <User className="h-4 w-4" />
                Inny
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="notes">Notatki</Label>
        <Textarea
          id="notes"
          value={formData.notes}
          onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          placeholder="Dodatkowe informacje o kontakcie..."
          className="rounded-xl min-h-[80px]"
        />
      </div>

      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline" onClick={onCancel} className="rounded-xl">
            Anuluj
          </Button>
        </DialogClose>
        <Button type="submit" className="rounded-xl">
          {contact ? 'Zapisz zmiany' : 'Dodaj kontakt'}
        </Button>
      </DialogFooter>
    </form>
  );
}

function ContactCard({
  contact,
  onEdit,
  onDelete,
  onTimeline,
}: {
  contact: Contact;
  onEdit: (contact: Contact) => void;
  onDelete: (id: string) => void;
  onTimeline: (contact: Contact) => void;
}) {
  const safeName = (contact.name || '').trim() || 'Kontakt';
  const contactType = (contact.type && typeConfig[contact.type]) ? contact.type : 'other';

  const initials = safeName
    .split(' ')
    .filter(Boolean)
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'K';

  const TypeIcon = typeConfig[contactType].icon;

  return (
    <Card className="card-hover group">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <Avatar className="h-14 w-14 ring-2 ring-primary/10">
              <AvatarFallback className="bg-gradient-to-br from-primary to-primary/70 text-primary-foreground text-lg font-semibold">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div>
              <h3 className="font-semibold text-lg group-hover:text-primary transition-colors text-safe-wrap">
                {safeName}
              </h3>
              <Badge variant="secondary" className={cn('text-[10px] mt-1', typeConfig[contactType].class)}>
                <TypeIcon className="h-3 w-3 mr-1" />
                {typeLabels[contactType]}
              </Badge>
            </div>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onTimeline(contact)}>
                <History className="mr-2 h-4 w-4" />
                Timeline
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(contact)}>
                <Edit className="mr-2 h-4 w-4" />
                Edytuj
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onDelete(contact.id)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Usuń
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <Separator className="my-4" />

        <div className="space-y-2">
          {contact.phone && (
            <a 
              href={`tel:${contact.phone}`} 
              className="flex items-center gap-3 text-sm group/link hover:text-primary transition-colors"
            >
              <div className="p-2 rounded-lg bg-muted">
                <Phone className="h-4 w-4 text-muted-foreground" />
              </div>
              <span className="hover:underline">{contact.phone}</span>
            </a>
          )}
          {contact.email && (
            <a 
              href={`mailto:${contact.email}`} 
              className="flex items-center gap-3 text-sm group/link hover:text-primary transition-colors"
            >
              <div className="p-2 rounded-lg bg-muted">
                <Mail className="h-4 w-4 text-muted-foreground" />
              </div>
              <span className="hover:underline truncate">{contact.email}</span>
            </a>
          )}
          {contact.notes && (
            <div className="flex items-start gap-3 text-sm mt-3">
              <div className="p-2 rounded-lg bg-muted">
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground line-clamp-2">{contact.notes}</p>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="flex gap-2 mt-4">
          {contact.phone && (
            <Button variant="outline" size="sm" className="flex-1 rounded-lg" asChild>
              <a href={`tel:${contact.phone}`}>
                <Phone className="mr-1 h-3.5 w-3.5" />
                Zadzwoń
              </a>
            </Button>
          )}
          {contact.email && (
            <Button variant="outline" size="sm" className="flex-1 rounded-lg" asChild>
              <a href={`mailto:${contact.email}`}>
                <Mail className="mr-1 h-3.5 w-3.5" />
                Email
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ContactsSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <Card key={i}>
          <CardContent className="p-5">
            <div className="flex items-center gap-4">
              <Skeleton className="h-14 w-14 rounded-full" />
              <div className="space-y-2">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-16" />
              </div>
            </div>
            <Skeleton className="h-px w-full my-4" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function Contacts() {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [timelineContact, setTimelineContact] = useState<Contact | null>(null);
  const [timelineNote, setTimelineNote] = useState('');
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: contacts, isLoading, error } = useQuery({
    queryKey: ['contacts'],
    queryFn: contactsApi.getAll,
  });

  const { data: timelineEvents } = useQuery({
    queryKey: ['contact-timeline', timelineContact?.id],
    queryFn: () => contactTimelineApi.getAll(timelineContact!.id),
    enabled: !!timelineContact,
  });

  const createMutation = useMutation({
    mutationFn: contactsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      toast.success('Kontakt dodany');
      setIsAddDialogOpen(false);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd dodawania kontaktu');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Contact> }) =>
      contactsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      toast.success('Kontakt zaktualizowany');
      setEditingContact(null);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd aktualizacji kontaktu');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: contactsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      toast.success('Kontakt usunięty');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd usuwania kontaktu');
    },
  });

  const addTimelineMutation = useMutation({
    mutationFn: ({ contactId, message }: { contactId: string; message: string }) =>
      contactTimelineApi.add(contactId, { type: 'note', message }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact-timeline', timelineContact?.id] });
      setTimelineNote('');
      toast.success('Dodano wpis do historii kontaktu');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd zapisu historii');
    },
  });

  const filteredContacts = contacts?.filter((contact) => {
    const name = (contact.name || '').toLowerCase();
    const email = (contact.email || '').toLowerCase();
    const phone = contact.phone || '';

    const matchesSearch = search
      ? name.includes(search.toLowerCase()) ||
        email.includes(search.toLowerCase()) ||
        phone.includes(search)
      : true;
    
    const matchesType = typeFilter === 'all' ? true : (contact.type || 'other') === typeFilter;
    
    return matchesSearch && matchesType;
  });

  const handleCreate = (data: Partial<Contact>) => {
    createMutation.mutate(data);
  };

  const handleUpdate = (data: Partial<Contact>) => {
    if (editingContact) {
      updateMutation.mutate({ id: editingContact.id, data });
    }
  };

  const handleDelete = (id: string) => {
    if (confirm('Czy na pewno chcesz usunąć ten kontakt?')) {
      deleteMutation.mutate(id);
    }
  };

  // Stats
  const stats = {
    total: contacts?.length || 0,
    clients: contacts?.filter(c => c.type === 'client').length || 0,
    owners: contacts?.filter(c => c.type === 'owner').length || 0,
    partners: contacts?.filter(c => c.type === 'partner').length || 0,
  };

  if (error) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Kontakty</h1>
            <p className="text-muted-foreground">Zarządzaj bazą klientów i partnerów</p>
          </div>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Nie udało się pobrać kontaktów. Spróbuj odświeżyć stronę.
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
          <h1 className="text-3xl font-bold tracking-tight">Kontakty</h1>
          <p className="text-muted-foreground">Zarządzaj bazą klientów i partnerów</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-xl">
              <Plus className="mr-2 h-4 w-4" />
              Nowy kontakt
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Dodaj nowy kontakt</DialogTitle>
              <DialogDescription>
                Wprowadź dane nowego kontaktu do systemu.
              </DialogDescription>
            </DialogHeader>
            <ContactForm
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
        <Card className="card-hover bg-gradient-to-br from-emerald-500/10 to-emerald-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Klienci</p>
            <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{stats.clients}</p>
          </CardContent>
        </Card>
        <Card className="card-hover bg-gradient-to-br from-amber-500/10 to-amber-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Właściciele</p>
            <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">{stats.owners}</p>
          </CardContent>
        </Card>
        <Card className="card-hover bg-gradient-to-br from-purple-500/10 to-purple-600/5">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Partnerzy</p>
            <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">{stats.partners}</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="card-hover">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Szukaj kontaktów..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 rounded-xl"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-full sm:w-48 rounded-xl">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Typ kontaktu" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Wszystkie typy</SelectItem>
                <SelectItem value="client">Klienci</SelectItem>
                <SelectItem value="owner">Właściciele</SelectItem>
                <SelectItem value="partner">Partnerzy</SelectItem>
                <SelectItem value="other">Inni</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Contacts Grid */}
      {isLoading ? (
        <ContactsSkeleton />
      ) : filteredContacts?.length === 0 ? (
        <Card className="card-hover">
          <CardContent className="p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
              <Users className="h-10 w-10 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Brak kontaktów</h3>
            <p className="text-muted-foreground mb-4 max-w-md mx-auto">
              {search || typeFilter !== 'all'
                ? 'Nie znaleziono kontaktów pasujących do wybranych filtrów'
                : 'Nie masz jeszcze żadnych kontaktów w systemie. Dodaj pierwszy kontakt, aby rozpocząć.'}
            </p>
            <Button onClick={() => setIsAddDialogOpen(true)} className="rounded-xl">
              <Plus className="mr-2 h-4 w-4" />
              Dodaj kontakt
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredContacts?.map((contact) => (
            <ContactCard
              key={contact.id}
              contact={contact}
              onEdit={setEditingContact}
              onDelete={handleDelete}
              onTimeline={setTimelineContact}
            />
          ))}
        </div>
      )}

      {/* Timeline Dialog */}
      <Dialog open={!!timelineContact} onOpenChange={() => setTimelineContact(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Historia kontaktu: {timelineContact?.name}</DialogTitle>
            <DialogDescription>Notatki i interakcje z klientem.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 max-h-72 overflow-auto">
            {timelineEvents?.length ? (
              timelineEvents.map((e: any) => (
                <div key={e.id} className="rounded-lg border p-3 text-sm">
                  <div className="text-muted-foreground text-xs mb-1">
                    {new Date(e.created_at || e.updated_at || Date.now()).toLocaleString('pl-PL')}
                  </div>
                  <div className="font-medium text-xs uppercase tracking-wide text-muted-foreground mb-1">{e.type || 'note'}</div>
                  <div>{e.message || '(brak treści)'}</div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">Brak wpisów historii.</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="timeline_note">Dodaj wpis</Label>
            <Textarea
              id="timeline_note"
              value={timelineNote}
              onChange={(e) => setTimelineNote(e.target.value)}
              placeholder="Np. Rozmowa tel. — klient chce 3 pokoje, budżet 750k"
              className="rounded-xl"
            />
          </div>
          <DialogFooter>
            <Button
              onClick={() => timelineContact && timelineNote.trim() && addTimelineMutation.mutate({ contactId: timelineContact.id, message: timelineNote.trim() })}
              className="rounded-xl"
              disabled={!timelineNote.trim() || addTimelineMutation.isPending}
            >
              {addTimelineMutation.isPending ? 'Zapisywanie...' : 'Zapisz wpis'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={!!editingContact} onOpenChange={() => setEditingContact(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edytuj kontakt</DialogTitle>
            <DialogDescription>
              Zmień dane kontaktu w systemie.
            </DialogDescription>
          </DialogHeader>
          {editingContact && (
            <ContactForm
              contact={editingContact}
              onSubmit={handleUpdate}
              onCancel={() => setEditingContact(null)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
