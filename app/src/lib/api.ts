import axios, { type AxiosError, type AxiosInstance } from 'axios';
import type { Listing, Contact, Task, DashboardStats, ApiError } from '@/types';

export interface ListingsPageResponse {
  total: number;
  page: number;
  limit: number;
  pages: number;
  data: Listing[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
const USE_LOCAL_DATA = import.meta.env.VITE_USE_LOCAL_DATA === 'true';

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Local data cache
let localListings: Listing[] | null = null;
let localContacts: Contact[] | null = null;
let localTasks: Task[] | null = null;

// Load local listings data
async function loadLocalListings(): Promise<Listing[]> {
  if (localListings) return localListings;
  try {
    const response = await fetch('/data/listings.json');
    if (!response.ok) throw new Error('Failed to load listings');
    localListings = await response.json();
    return localListings || [];
  } catch (error) {
    console.error('Error loading local listings:', error);
    return [];
  }
}

// Generate mock contacts
function generateMockContacts(): Contact[] {
  const names = [
    "Anna Kowalska", "Jan Nowak", "Maria Wiśniewska", "Piotr Zieliński",
    "Katarzyna Lewandowska", "Tomasz Szymański", "Magdalena Woźniak",
    "Michał Dąbrowski", "Agnieszka Kozłowska", "Marcin Jankowski",
    "Barbara Wojciechowska", "Adam Kowalczyk", "Ewa Michalska",
    "Krzysztof Piotrowski", "Małgorzata Grabowska"
  ];
  
  const types: Contact['type'][] = ['client', 'owner', 'partner', 'other'];
  
  return names.map((name, i) => ({
    id: `contact_${i + 1}`,
    name,
    email: `${name.toLowerCase().replace(' ', '.')}@example.com`,
    phone: `+48 ${500 + Math.floor(Math.random() * 499)} ${String(Math.floor(Math.random() * 999)).padStart(3, '0')} ${String(Math.floor(Math.random() * 999)).padStart(3, '0')}`,
    type: types[i % types.length],
    notes: i % 3 === 0 ? "Klient zainteresowany mieszkaniami w centrum. Budżet do 800k PLN." : undefined,
    created_at: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date().toISOString(),
  }));
}

// Generate mock tasks
function generateMockTasks(): Task[] {
  const titles = [
    "Skontaktować się z klientem w sprawie oferty",
    "Przygotować umowę pośrednictwa",
    "Zorganizować oglądanie mieszkania",
    "Wycenić nieruchomość",
    "Zaktualizować zdjęcia w ofercie",
    "Odpowiedzieć na zapytanie email",
    "Przygotować prezentację dla klienta",
    "Sprawdzić dokumentację nieruchomości",
    "Skontaktować się z właścicielem",
    "Przygotować raport miesięczny",
    "Zadzwonić do zainteresowanego klienta",
    "Zaktualizować cenę w ofercie"
  ];
  
  const priorities: Task['priority'][] = ['low', 'medium', 'high', 'urgent'];
  const statuses: Task['status'][] = ['pending', 'in_progress', 'completed', 'cancelled'];
  
  return titles.map((title, i) => {
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    const dueDate = new Date();
    dueDate.setDate(dueDate.getDate() + Math.floor(Math.random() * 14) - 3);
    
    return {
      id: `task_${i + 1}`,
      title,
      description: Math.random() > 0.5 ? "Szczegóły zadania do wykonania..." : undefined,
      status,
      priority: priorities[Math.floor(Math.random() * priorities.length)],
      due_date: dueDate.toISOString(),
      created_at: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
      updated_at: new Date().toISOString(),
    };
  });
}

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const apiError: ApiError = {
      message: 'Wystąpił błąd',
      status: error.response?.status,
    };

    if (error.response) {
      const data = error.response.data as any;
      apiError.message = data.detail || data.message || `Błąd ${error.response.status}`;
      apiError.code = data.code;
    } else if (error.request) {
      apiError.message = 'Brak połączenia z serwerem';
    }

    return Promise.reject(apiError);
  }
);

// Auth API
export const adminUsersApi = {
  list: async () => {
    const response = await api.get('/auth/admin/users');
    return response.data as { users: any[]; total: number };
  },
  activate: async (userId: string) => {
    const response = await api.post(`/auth/admin/users/${userId}/activate`);
    return response.data;
  },
  deactivate: async (userId: string) => {
    const response = await api.post(`/auth/admin/users/${userId}/deactivate`);
    return response.data;
  },
  setRole: async (userId: string, role: 'admin' | 'agent' | 'user') => {
    const response = await api.post(`/auth/admin/users/${userId}/role`, { role });
    return response.data;
  },
};

export const authApi = {
  login: async (email: string, password: string) => {
    const response = await api.post('/auth/login', { email, password });
    return response.data;
  },

  register: async (payload: { email: string; password: string; confirm_password: string; name?: string }) => {
    const response = await api.post('/auth/register', payload);
    return response.data;
  },

  bootstrapStatus: async () => {
    const response = await api.get('/auth/bootstrap-status');
    return response.data as { users_count: number; requires_bootstrap: boolean; hint: string };
  },

  bootstrapAdmin: async (payload: { email: string; password: string; name?: string; bootstrap_token: string }) => {
    const response = await api.post('/auth/bootstrap-admin', {
      email: payload.email,
      password: payload.password,
      name: payload.name,
    }, {
      headers: {
        'X-Bootstrap-Token': payload.bootstrap_token,
      },
    });
    return response.data;
  },

  requestPasswordReset: async (email: string) => {
    const response = await api.post('/auth/reset-password', { email });
    return response.data;
  },

  confirmPasswordReset: async (payload: { token: string; new_password: string; confirm_password: string }) => {
    const response = await api.post('/auth/reset-password/confirm', payload);
    return response.data;
  },
  
  logout: async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // no-op
    }
    localStorage.removeItem('auth_token');
  },
  
  getCurrentUser: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

type OfferApi = {
  id: string;
  source_id: string;
  fingerprint?: string;
  url?: string;
  title?: string;
  price?: string | number | null;
  currency?: string | null;
  city?: string | null;
  region?: string | null;
  area_m2?: number | string | null;
  rooms?: number | null;
  status?: string | null;
  raw_json?: Record<string, any> | null;
  source_created_at?: string | null;
  imported_at?: string | null;
  first_seen?: string;
  last_seen?: string;
};

function mapOfferStatus(status?: string | null): Listing['status'] {
  if (status === 'sold') return 'sold';
  if (status === 'active') return 'active';
  if (status === 'withdrawn' || status === 'expired' || status === 'invalid_parse') return 'archived';
  return 'active';
}

function mapOfferToListing(offer: OfferApi, sourceName?: string): Listing {
  return {
    id: offer.id,
    title: offer.title || 'Oferta',
    price: offer.price == null ? null : Number(offer.price),
    currency: offer.currency || 'PLN',
    city: offer.city || '',
    region: offer.region || undefined,
    district: undefined,
    street: undefined,
    area_sqm: offer.area_m2 ? Number(offer.area_m2) : undefined,
    rooms: offer.rooms ?? undefined,
    property_type: 'apartment',
    transaction_type: 'sale',
    status: mapOfferStatus(offer.status),
    source: sourceName,
    external_id: offer.fingerprint,
    url: offer.url,
    description: offer.raw_json?.description,
    images: Array.isArray(offer.raw_json?.images) ? offer.raw_json.images : undefined,
    features: undefined,
    created_at: offer.source_created_at || offer.first_seen || new Date().toISOString(),
    updated_at: offer.imported_at || offer.last_seen || new Date().toISOString(),
  };
}

// Listings API - uses local JSON data
export const listingsApi = {
  getPage: async (params?: {
    page?: number;
    limit?: number;
    offset?: number;
    source?: string;
    status?: string;
    sort?: 'date';
    order?: 'asc' | 'desc';
    date_from?: string;
    date_to?: string;
    city?: string;
    region?: string;
    search?: string;
  }): Promise<ListingsPageResponse> => {
    const page = params?.page || 1;
    const limit = params?.limit || 20;
    const offset = params?.offset ?? (page - 1) * limit;

    if (USE_LOCAL_DATA) {
      let listings = await loadLocalListings();

      if (params?.status && params.status !== 'all') listings = listings.filter((l) => l.status === params.status);
      if (params?.city) listings = listings.filter((l) => l.city?.toLowerCase().includes(params.city!.toLowerCase()));
      if (params?.region) listings = listings.filter((l) => l.region?.toLowerCase().includes(params.region!.toLowerCase()));
      if (params?.search) {
        const search = params.search.toLowerCase();
        listings = listings.filter((l) => l.title?.toLowerCase().includes(search) || l.city?.toLowerCase().includes(search) || l.district?.toLowerCase().includes(search));
      }

      const total = listings.length;
      const pages = Math.ceil(total / limit);
      const data = listings.slice(offset, offset + limit);
      return { total, page, limit, pages, data };
    }

    const [offersRes, sourcesRes] = await Promise.all([
      api.get('/offers', {
        params: {
          page,
          limit,
          offset,
          source: params?.source,
          status: params?.status && params?.status !== 'all' ? params.status : undefined,
          sort: params?.sort,
          order: params?.order,
          date_from: params?.date_from,
          date_to: params?.date_to,
        },
      }),
      api.get('/sources').catch(() => ({ data: [] } as any)),
    ]);

    const sourceById = new Map<string, string>((sourcesRes.data || []).map((s: any) => [s.id, s.name]));

    const rawItems = (offersRes.data?.data || offersRes.data?.items || []) as OfferApi[];
    let listings = rawItems.map((offer) => mapOfferToListing(offer, sourceById.get(offer.source_id)));

    if (params?.city) listings = listings.filter((l) => l.city?.toLowerCase().includes(params.city!.toLowerCase()));
    if (params?.region) listings = listings.filter((l) => l.region?.toLowerCase().includes(params.region!.toLowerCase()));
    if (params?.search) {
      const search = params.search.toLowerCase();
      listings = listings.filter((l) => l.title?.toLowerCase().includes(search) || l.city?.toLowerCase().includes(search) || l.district?.toLowerCase().includes(search));
    }

    const total = Number(offersRes.data?.total ?? listings.length);
    const resolvedPage = Number(offersRes.data?.page ?? page);
    const resolvedLimit = Number(offersRes.data?.limit ?? limit);
    const pages = Number(offersRes.data?.pages ?? Math.ceil(total / resolvedLimit));

    return {
      total,
      page: resolvedPage,
      limit: resolvedLimit,
      pages,
      data: listings,
    };
  },

  getAll: async (params?: { status?: string; city?: string; region?: string; search?: string }) => {
    const firstPage = await listingsApi.getPage({ ...params, page: 1, limit: 100 });
    return firstPage.data;
  },

  getCounts: async (params?: { source?: string }) => {
    if (USE_LOCAL_DATA) {
      const listings = await loadLocalListings();
      return {
        total: listings.length,
        active: listings.filter((l) => ['active', 'published'].includes(l.status)).length,
        reserved: listings.filter((l) => ['draft', 'reserved'].includes(l.status)).length,
        sold: listings.filter((l) => l.status === 'sold').length,
      };
    }

    const [allRes, activeRes, soldRes] = await Promise.all([
      api.get('/offers', { params: { limit: 1, page: 1, source: params?.source } }),
      api.get('/offers', { params: { limit: 1, page: 1, source: params?.source, status: 'active' } }),
      api.get('/offers', { params: { limit: 1, page: 1, source: params?.source, status: 'sold' } }),
    ]);

    const total = Number(allRes.data?.total || 0);
    const active = Number(activeRes.data?.total || 0);
    const sold = Number(soldRes.data?.total || 0);
    const reserved = Math.max(total - active - sold, 0);

    return { total, active, reserved, sold };
  },
  
  getById: async (id: string) => {
    if (USE_LOCAL_DATA) {
      const listings = await loadLocalListings();
      const listing = listings.find(l => l.id === id);
      if (!listing) throw new Error('Oferta nie znaleziona');
      return listing;
    }
    
    const [offerRes, sourcesRes] = await Promise.all([
      api.get(`/offers/${id}`),
      api.get('/sources').catch(() => ({ data: [] } as any)),
    ]);
    const sourceById = new Map<string, string>((sourcesRes.data || []).map((s: any) => [s.id, s.name]));
    return mapOfferToListing(offerRes.data as OfferApi, sourceById.get((offerRes.data as OfferApi).source_id));
  },
  
  updateStatus: async (id: string, status: Listing['status']) => {
    if (USE_LOCAL_DATA) {
      const listings = await loadLocalListings();
      const listing = listings.find(l => l.id === id);
      if (listing) {
        listing.status = status;
        listing.updated_at = new Date().toISOString();
      }
      return listing!;
    }
    
    const response = await api.patch(`/listings/${id}`, { status });
    return response.data as Listing;
  },
  
  create: async (data: Partial<Listing>) => {
    if (USE_LOCAL_DATA) {
      const listings = await loadLocalListings();
      const newListing: Listing = {
        id: `listing_${Date.now()}`,
        title: data.title || '',
        price: data.price || 0,
        currency: data.currency || 'PLN',
        city: data.city || '',
        district: data.district,
        street: data.street,
        area_sqm: data.area_sqm,
        rooms: data.rooms,
        floor: data.floor,
        total_floors: data.total_floors,
        year_built: data.year_built,
        property_type: data.property_type || 'apartment',
        transaction_type: data.transaction_type || 'sale',
        status: data.status || 'draft',
        source: data.source,
        external_id: data.external_id,
        description: data.description,
        features: data.features,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      listings.unshift(newListing);
      return newListing;
    }
    
    const response = await api.post('/listings', data);
    return response.data as Listing;
  },
  
  update: async (id: string, data: Partial<Listing>) => {
    if (USE_LOCAL_DATA) {
      const listings = await loadLocalListings();
      const listing = listings.find(l => l.id === id);
      if (listing) {
        Object.assign(listing, { ...data, updated_at: new Date().toISOString() });
      }
      return listing!;
    }
    
    const response = await api.patch(`/listings/${id}`, data);
    return response.data as Listing;
  },
  
  delete: async (id: string) => {
    if (USE_LOCAL_DATA) {
      const listings = await loadLocalListings();
      const index = listings.findIndex(l => l.id === id);
      if (index > -1) {
        listings.splice(index, 1);
      }
      return;
    }
    
    await api.delete(`/listings/${id}`);
  },
};

export const sourcesApi = {
  getAll: async () => {
    const response = await api.get('/sources');
    return response.data || [];
  },
};

// Contacts API - uses mock data
export const contactsApi = {
  getAll: async () => {
    if (USE_LOCAL_DATA) {
      if (!localContacts) {
        localContacts = generateMockContacts();
      }
      return localContacts;
    }
    
    const response = await api.get('/contacts');
    return response.data.contacts as Contact[];
  },
  
  getById: async (id: string) => {
    if (USE_LOCAL_DATA) {
      const contacts = await contactsApi.getAll();
      const contact = contacts.find(c => c.id === id);
      if (!contact) throw new Error('Kontakt nie znaleziony');
      return contact;
    }
    
    const response = await api.get(`/contacts/${id}`);
    return response.data as Contact;
  },
  
  create: async (data: Partial<Contact>) => {
    if (USE_LOCAL_DATA) {
      const contacts = await contactsApi.getAll();
      const newContact: Contact = {
        id: `contact_${Date.now()}`,
        name: data.name || '',
        email: data.email,
        phone: data.phone,
        type: data.type || 'client',
        notes: data.notes,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      contacts.unshift(newContact);
      return newContact;
    }
    
    const response = await api.post('/contacts', data);
    return response.data as Contact;
  },
  
  update: async (id: string, data: Partial<Contact>) => {
    if (USE_LOCAL_DATA) {
      const contacts = await contactsApi.getAll();
      const contact = contacts.find(c => c.id === id);
      if (contact) {
        Object.assign(contact, { ...data, updated_at: new Date().toISOString() });
      }
      return contact!;
    }
    
    const response = await api.patch(`/contacts/${id}`, data);
    return response.data as Contact;
  },
  
  delete: async (id: string) => {
    if (USE_LOCAL_DATA) {
      const contacts = await contactsApi.getAll();
      const index = contacts.findIndex(c => c.id === id);
      if (index > -1) {
        contacts.splice(index, 1);
      }
      return;
    }
    
    await api.delete(`/contacts/${id}`);
  },
};

// Tasks API - uses mock data
export const tasksApi = {
  getAll: async (params?: { status?: string; assigned_to?: string }) => {
    if (USE_LOCAL_DATA) {
      if (!localTasks) {
        localTasks = generateMockTasks();
      }
      
      let tasks = localTasks;
      
      if (params?.status) {
        tasks = tasks.filter(t => t.status === params.status);
      }
      
      return tasks;
    }
    
    const response = await api.get('/tasks', { params });
    return response.data.tasks as Task[];
  },
  
  getById: async (id: string) => {
    if (USE_LOCAL_DATA) {
      const tasks = await tasksApi.getAll();
      const task = tasks.find(t => t.id === id);
      if (!task) throw new Error('Zadanie nie znalezione');
      return task;
    }
    
    const response = await api.get(`/tasks/${id}`);
    return response.data as Task;
  },
  
  create: async (data: Partial<Task>) => {
    if (USE_LOCAL_DATA) {
      const tasks = await tasksApi.getAll();
      const newTask: Task = {
        id: `task_${Date.now()}`,
        title: data.title || '',
        description: data.description,
        status: data.status || 'pending',
        priority: data.priority || 'medium',
        due_date: data.due_date,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      tasks.unshift(newTask);
      return newTask;
    }
    
    const response = await api.post('/tasks', data);
    return response.data as Task;
  },
  
  update: async (id: string, data: Partial<Task>) => {
    if (USE_LOCAL_DATA) {
      const tasks = await tasksApi.getAll();
      const task = tasks.find(t => t.id === id);
      if (task) {
        Object.assign(task, { ...data, updated_at: new Date().toISOString() });
      }
      return task!;
    }
    
    const response = await api.patch(`/tasks/${id}`, data);
    return response.data as Task;
  },
  
  updateStatus: async (id: string, status: Task['status']) => {
    if (USE_LOCAL_DATA) {
      const tasks = await tasksApi.getAll();
      const task = tasks.find(t => t.id === id);
      if (task) {
        task.status = status;
        task.updated_at = new Date().toISOString();
      }
      return task!;
    }
    
    const response = await api.patch(`/tasks/${id}`, { status });
    return response.data as Task;
  },
  
  complete: async (id: string, notes?: string) => {
    if (USE_LOCAL_DATA) {
      const tasks = await tasksApi.getAll();
      const task = tasks.find(t => t.id === id);
      if (task) {
        task.status = 'completed';
        task.completed_at = new Date().toISOString();
        task.updated_at = new Date().toISOString();
      }
      return task!;
    }
    
    const response = await api.post(`/tasks/${id}/complete`, { notes });
    return response.data as Task;
  },
  
  delete: async (id: string) => {
    if (USE_LOCAL_DATA) {
      const tasks = await tasksApi.getAll();
      const index = tasks.findIndex(t => t.id === id);
      if (index > -1) {
        tasks.splice(index, 1);
      }
      return;
    }
    
    await api.delete(`/tasks/${id}`);
  },
  
  getDashboard: async (_userId: string) => {
    const tasks = await tasksApi.getAll();
    return {
      total: tasks.length,
      pending: tasks.filter(t => t.status === 'pending').length,
      in_progress: tasks.filter(t => t.status === 'in_progress').length,
      completed: tasks.filter(t => t.status === 'completed').length,
      overdue: tasks.filter(t => 
        t.due_date && new Date(t.due_date) < new Date() && t.status !== 'completed'
      ).length,
    };
  },
};

export type CalendarEventApi = {
  id: string;
  title: string;
  event_type: 'call' | 'meeting' | 'presentation' | 'other' | 'viewing' | 'task';
  start_at: string;
  end_at: string;
  contact_name?: string;
  listing_title?: string;
  location?: string;
  description?: string;
  status: 'scheduled' | 'completed' | 'cancelled';
  reminder_minutes?: number;
  created_at?: string;
  updated_at?: string;
};

export const calendarApi = {
  getRange: async (params?: { from?: string; to?: string }) => {
    const response = await api.get('/calendar', { params });
    return (response.data?.events || []) as CalendarEventApi[];
  },

  getById: async (id: string) => {
    const response = await api.get(`/calendar/${id}`);
    return response.data as CalendarEventApi;
  },

  create: async (payload: Partial<CalendarEventApi>) => {
    const response = await api.post('/calendar', payload);
    return response.data as CalendarEventApi;
  },

  update: async (id: string, payload: Partial<CalendarEventApi>) => {
    const response = await api.patch(`/calendar/${id}`, payload);
    return response.data as CalendarEventApi;
  },

  delete: async (id: string) => {
    await api.delete(`/calendar/${id}`);
  },
};

export type DocumentApi = {
  id: string;
  name: string;
  mime_type?: string;
  size_bytes?: number;
  related_to?: string;
  uploaded_by?: string;
  created_at?: string;
};

export const documentsApi = {
  list: async (params?: { limit?: number; offset?: number; q?: string }) => {
    const response = await api.get('/documents', { params });
    return response.data as {
      documents: DocumentApi[];
      stats: { total: number; pdf: number; images: number; total_size_bytes: number };
      total: number;
      limit: number;
      offset: number;
    };
  },

  upload: async (files: File[], relatedTo?: string, onProgress?: (percent: number) => void) => {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    if (relatedTo) form.append('related_to', relatedTo);

    const response = await api.post('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (evt) => {
        if (!onProgress || !evt.total) return;
        onProgress(Math.round((evt.loaded / evt.total) * 100));
      },
    });
    return response.data;
  },

  deleteOne: async (id: string) => {
    await api.delete(`/documents/${id}`);
  },

  deleteBulk: async (ids: string[]) => {
    const response = await api.post('/documents/bulk-delete', { ids });
    return response.data;
  },

  deleteAll: async () => {
    const response = await api.delete('/documents', { params: { confirm: true } });
    return response.data;
  },

  downloadOneUrl: (id: string) => `${API_BASE_URL}/documents/${id}/download`,

  bulkDownload: async (ids: string[]) => {
    const response = await api.post('/documents/bulk-download', { ids }, { responseType: 'blob' });
    return response.data as Blob;
  },
};

export type NotificationApi = {
  id: string;
  type: string;
  title: string;
  message: string;
  entity_type?: string;
  entity_id?: string;
  is_read: boolean;
  created_at: string;
};

export const notificationsApi = {
  list: async (params?: { limit?: number; offset?: number; unread_only?: boolean }) => {
    const response = await api.get('/notifications', { params });
    return response.data as { items: NotificationApi[]; total: number; unread_count: number; limit: number; offset: number };
  },
  markRead: async (id: string) => {
    const response = await api.post(`/notifications/${id}/read`);
    return response.data;
  },
  markAllRead: async () => {
    const response = await api.post('/notifications/mark-all-read');
    return response.data;
  },
};

export const profileApi = {
  get: async () => {
    const response = await api.get('/user/profile');
    return response.data;
  },
  uploadAvatar: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post('/profile/avatar', form, { headers: { 'Content-Type': 'multipart/form-data' } });
    return response.data;
  },
  uploadCover: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post('/user/cover', form, { headers: { 'Content-Type': 'multipart/form-data' } });
    return response.data;
  },
  removeCover: async () => {
    const response = await api.delete('/user/cover');
    return response.data;
  },
  changePassword: async (payload: { current_password: string; new_password: string; confirm_password: string }) => {
    const response = await api.post('/auth/change-password', payload);
    return response.data;
  },
};

// Dashboard API - uses calculated data
export const dashboardApi = {
  getDashboard: async () => {
    const response = await api.get('/dashboard');
    return response.data;
  },

  getStats: async () => {
    if (USE_LOCAL_DATA) {
      const listings = await listingsApi.getAll();
      const contacts = await contactsApi.getAll();
      const tasks = await tasksApi.getAll();
      const now = new Date();
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      return {
        total_listings: listings.length,
        active_listings: listings.filter(l => l.status === 'published' || l.status === 'active').length,
        new_this_week: listings.filter(l => new Date(l.created_at) > weekAgo).length,
        price_changes: 0,
        total_contacts: contacts.length,
        pending_tasks: tasks.filter(t => t.status === 'pending').length,
        overdue_tasks: tasks.filter(t => t.due_date && new Date(t.due_date) < now && t.status !== 'completed').length,
      } as DashboardStats;
    }

    const payload = await dashboardApi.getDashboard();
    return {
      total_listings: Number(payload.offers_total || 0),
      active_listings: Number(payload.offers_active || 0),
      new_this_week: Number(payload.offers_last_week || 0),
      price_changes: 0,
      total_contacts: Number(payload.contacts_total || 0),
      pending_tasks: Number(payload.tasks_pending || 0),
      overdue_tasks: Number(payload.tasks_overdue || 0),
    } as DashboardStats;
  },

  getRecentActivity: async () => {
    if (USE_LOCAL_DATA) {
      const listings = await listingsApi.getAll();
      return listings.slice(0, 5).map(l => ({
        id: l.id,
        type: 'listing_created',
        title: `Nowa oferta: ${l.title}`,
        description: `${l.city}, ${l.price?.toLocaleString('pl-PL')} PLN`,
        created_at: l.created_at,
      }));
    }

    const payload = await dashboardApi.getDashboard();
    return (payload.recent_activity || []).map((a: any) => ({
      id: a.id,
      type: a.entity || a.action || 'activity',
      title: a.description || `${a.action || 'Akcja'}: ${a.entity || 'system'}`,
      description: `${a.entity || '-'} #${a.entity_id || '-'}`,
      created_at: a.created_at,
    }));
  },
};

// Leads API
export const leadsApi = {
  getAll: async (params?: { status?: string }) => {
    const response = await api.get('/leads', { params });
    return response.data.leads || [];
  },
  create: async (data: Record<string, any>) => {
    const response = await api.post('/leads', data);
    return response.data;
  },
  update: async (id: string, data: Record<string, any>) => {
    const response = await api.patch(`/leads/${id}`, data);
    return response.data;
  },
};

// CRM timeline API
export const contactTimelineApi = {
  getAll: async (contactId: string) => {
    const response = await api.get(`/contacts/${contactId}/timeline`);
    return response.data.events || [];
  },
  add: async (contactId: string, data: Record<string, any>) => {
    const response = await api.post(`/contacts/${contactId}/timeline`, data);
    return response.data;
  },
};

// Follow-up workflow API
export const followupsApi = {
  getAll: async () => {
    const response = await api.get('/workflow/followups');
    return response.data.items || [];
  },
  remind: async (taskId: string, reminder_at: string) => {
    const response = await api.post(`/workflow/followups/${taskId}/remind`, { reminder_at });
    return response.data;
  },
};

// Scrape control API
export const scrapeApi = {
  trigger: async (source?: string) => {
    const response = await api.post('/scrape/trigger', null, {
      params: source ? { source } : undefined,
    });
    return response.data;
  },
};

// Audit logs API
export const auditLogsApi = {
  getAll: async (limit = 100) => {
    const response = await api.get('/audit-logs', { params: { limit } });
    return {
      items: response.data.items || [],
      total: response.data.total || 0,
    };
  },
};

// Health check
export type PropertyApi = {
  id: string;
  title: string;
  city?: string;
  price?: number;
  crm_status?: string;
};

export const propertiesApi = {
  getAll: async (params?: { status?: string }) => {
    const response = await api.get('/properties', { params });
    return (response.data?.properties || []) as PropertyApi[];
  },
  getById: async (id: string) => {
    const response = await api.get(`/properties/${id}`);
    return response.data as Record<string, any>;
  },
  getImages: async (id: string) => {
    const response = await api.get(`/properties/${id}/images`);
    return response.data?.images || [];
  },
};

export type OtodomPublicationInfo = {
  publication_status: string;
  external_listing_id?: string | null;
  last_synced_at?: string | null;
  last_error?: string | null;
  attempts?: number;
};

export const otodomApi = {
  publish: async (propertyId: string) => {
    const response = await api.post(`/api/properties/${propertyId}/publish/otodom`);
    return response.data;
  },
  sync: async (propertyId: string) => {
    const response = await api.post(`/api/properties/${propertyId}/sync/otodom`);
    return response.data;
  },
  unpublish: async (propertyId: string) => {
    const response = await api.post(`/api/properties/${propertyId}/unpublish/otodom`);
    return response.data;
  },
  getPublication: async (propertyId: string): Promise<OtodomPublicationInfo> => {
    const response = await api.get(`/api/properties/${propertyId}/publication/otodom`);
    return response.data;
  },
  getLogs: async (propertyId: string) => {
    const response = await api.get(`/api/properties/${propertyId}/publication/otodom/logs`);
    return response.data as { logs: any[]; jobs: any[] };
  },
};

export const healthApi = {
  check: async () => {
    if (USE_LOCAL_DATA) {
      return { status: 'healthy', mode: 'local_data' };
    }
    
    const response = await api.get('/health');
    return response.data;
  },
};

export default api;
