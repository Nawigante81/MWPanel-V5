// Types for Real Estate Monitor

export interface Listing {
  id: string;
  title: string;
  price: number | null;
  currency: string;
  city: string;
  region?: string;
  district?: string;
  street?: string;
  zip_code?: string;
  country?: string;
  area_sqm?: number;
  rooms?: number;
  bathrooms?: number;
  floor?: number;
  total_floors?: number;
  year_built?: number;
  property_type: 'apartment' | 'house' | 'land' | 'commercial' | 'other';
  transaction_type: 'sale' | 'rent';
  status: 'draft' | 'published' | 'archived' | 'sold' | 'rented' | 'active' | 'inactive' | 'reserved';
  source?: string;
  external_id?: string;
  url?: string;
  description?: string;
  images?: string[];
  features?: string[];
  created_at: string;
  updated_at: string;
  owner_name?: string;
  owner_phone?: string;
  owner_email?: string;
  commission_percent?: number;
}

export interface Contact {
  id: string;
  name: string;
  phone?: string;
  email?: string;
  type: 'client' | 'owner' | 'partner' | 'other';
  notes?: string;
  preferences?: {
    property_types?: string[];
    cities?: string[];
    price_min?: number;
    price_max?: number;
  };
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  assigned_to?: string;
  created_by?: string;
  due_date?: string;
  completed_at?: string;
  related_type?: 'listing' | 'contact' | 'viewing' | 'commission' | 'general';
  related_id?: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'agent' | 'viewer';
  avatar?: string;
}

export interface DashboardStats {
  total_listings: number;
  active_listings: number;
  new_this_week: number;
  price_changes: number;
  total_contacts: number;
  pending_tasks: number;
  overdue_tasks: number;
}

export interface ApiError {
  message: string;
  code?: string;
  status?: number;
}
