import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listingsApi } from '@/lib/api';
import type { Listing } from '@/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ArrowLeft,
  Save,
  Building2,
  MapPin,
  Euro,
  Home,
  BedDouble,
  Bath,
  Maximize,
  Calendar,
  Tag,
  FileText,
  X,
  Plus,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const propertyTypes = [
  { value: 'apartment', label: 'Mieszkanie' },
  { value: 'house', label: 'Dom' },
  { value: 'commercial', label: 'Lokal użytkowy' },
  { value: 'land', label: 'Działka' },
  { value: 'garage', label: 'Garaż' },
];

const transactionTypes = [
  { value: 'sale', label: 'Sprzedaż' },
  { value: 'rent', label: 'Wynajem' },
];

const statuses = [
  { value: 'draft', label: 'Szkic' },
  { value: 'published', label: 'Opublikowana' },
  { value: 'archived', label: 'Archiwalna' },
  { value: 'sold', label: 'Sprzedana' },
  { value: 'rented', label: 'Wynajęta' },
];

interface FormData {
  title: string;
  description: string;
  property_type: string;
  transaction_type: string;
  status: string;
  price: string;
  currency: string;
  area_sqm: string;
  rooms: string;
  bathrooms: string;
  floor: string;
  total_floors: string;
  year_built: string;
  city: string;
  district: string;
  street: string;
  zip_code: string;
  country: string;
  source: string;
  external_id: string;
  features: string[];
}

const initialFormData: FormData = {
  title: '',
  description: '',
  property_type: 'apartment',
  transaction_type: 'sale',
  status: 'draft',
  price: '',
  currency: 'PLN',
  area_sqm: '',
  rooms: '',
  bathrooms: '',
  floor: '',
  total_floors: '',
  year_built: '',
  city: '',
  district: '',
  street: '',
  zip_code: '',
  country: 'Polska',
  source: '',
  external_id: '',
  features: [],
};

export default function ListingForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isEditing = !!id;

  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [newFeature, setNewFeature] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Fetch listing data if editing
  const { data: listing, isLoading } = useQuery({
    queryKey: ['listing', id],
    queryFn: () => listingsApi.getById(id!),
    enabled: isEditing,
  });

  // Populate form when editing
  useEffect(() => {
    if (listing) {
      setFormData({
        title: listing.title || '',
        description: listing.description || '',
        property_type: listing.property_type || 'apartment',
        transaction_type: listing.transaction_type || 'sale',
        status: listing.status || 'draft',
        price: listing.price?.toString() || '',
        currency: listing.currency || 'PLN',
        area_sqm: listing.area_sqm?.toString() || '',
        rooms: listing.rooms?.toString() || '',
        bathrooms: listing.bathrooms?.toString() || '',
        floor: listing.floor?.toString() || '',
        total_floors: listing.total_floors?.toString() || '',
        year_built: listing.year_built?.toString() || '',
        city: listing.city || '',
        district: listing.district || '',
        street: listing.street || '',
        zip_code: listing.zip_code || '',
        country: listing.country || 'Polska',
        source: listing.source || '',
        external_id: listing.external_id || '',
        features: listing.features || [],
      });
    }
  }, [listing]);

  const createMutation = useMutation({
    mutationFn: (data: Partial<Listing>) => listingsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      toast.success('Oferta została utworzona');
      navigate('/listings');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd tworzenia oferty');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Listing> }) =>
      listingsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['listings'] });
      queryClient.invalidateQueries({ queryKey: ['listing', id] });
      toast.success('Oferta została zaktualizowana');
      navigate('/listings');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Błąd aktualizacji oferty');
    },
  });

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.title.trim()) {
      newErrors.title = 'Tytuł jest wymagany';
    }
    if (!formData.city.trim()) {
      newErrors.city = 'Miasto jest wymagane';
    }
    if (!formData.price || parseFloat(formData.price) <= 0) {
      newErrors.price = 'Cena musi być większa od 0';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      toast.error('Proszę wypełnić wymagane pola');
      return;
    }

    const data: Partial<Listing> = {
      title: formData.title,
      description: formData.description,
      property_type: formData.property_type as Listing['property_type'],
      transaction_type: formData.transaction_type as Listing['transaction_type'],
      status: formData.status as Listing['status'],
      price: parseFloat(formData.price),
      currency: formData.currency,
      area_sqm: formData.area_sqm ? parseFloat(formData.area_sqm) : undefined,
      rooms: formData.rooms ? parseInt(formData.rooms) : undefined,
      bathrooms: formData.bathrooms ? parseInt(formData.bathrooms) : undefined,
      floor: formData.floor ? parseInt(formData.floor) : undefined,
      total_floors: formData.total_floors ? parseInt(formData.total_floors) : undefined,
      year_built: formData.year_built ? parseInt(formData.year_built) : undefined,
      city: formData.city,
      district: formData.district,
      street: formData.street,
      zip_code: formData.zip_code,
      country: formData.country,
      source: formData.source,
      external_id: formData.external_id,
      features: formData.features,
    };

    if (isEditing) {
      updateMutation.mutate({ id: id!, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleChange = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: '' }));
    }
  };

  const addFeature = () => {
    if (newFeature.trim() && !formData.features.includes(newFeature.trim())) {
      setFormData((prev) => ({
        ...prev,
        features: [...prev.features, newFeature.trim()],
      }));
      setNewFeature('');
    }
  };

  const removeFeature = (feature: string) => {
    setFormData((prev) => ({
      ...prev,
      features: prev.features.filter((f) => f !== feature),
    }));
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <Card>
          <CardContent className="p-6 space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-32 w-full" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => navigate('/listings')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {isEditing ? 'Edytuj ofertę' : 'Nowa oferta'}
            </h1>
            <p className="text-muted-foreground">
              {isEditing ? 'Zaktualizuj dane nieruchomości' : 'Dodaj nową nieruchomość do systemu'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => navigate('/listings')}>
            Anuluj
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending || updateMutation.isPending}>
            <Save className="mr-2 h-4 w-4" />
            {createMutation.isPending || updateMutation.isPending ? 'Zapisywanie...' : 'Zapisz'}
          </Button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Home className="h-5 w-5" />
              Podstawowe informacje
            </CardTitle>
            <CardDescription>Wprowadź główne dane o nieruchomości</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">
                Tytuł oferty <span className="text-destructive">*</span>
              </Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => handleChange('title', e.target.value)}
                placeholder="Np. Przestronne mieszkanie w centrum"
                className={cn(errors.title && 'border-destructive')}
              />
              {errors.title && <p className="text-sm text-destructive">{errors.title}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Opis</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                placeholder="Szczegółowy opis nieruchomości..."
                rows={4}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Typ nieruchomości</Label>
                <Select
                  value={formData.property_type}
                  onValueChange={(value) => handleChange('property_type', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {propertyTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Typ transakcji</Label>
                <Select
                  value={formData.transaction_type}
                  onValueChange={(value) => handleChange('transaction_type', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {transactionTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={formData.status}
                  onValueChange={(value) => handleChange('status', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {statuses.map((status) => (
                      <SelectItem key={status.value} value={status.value}>
                        {status.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Price */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Euro className="h-5 w-5" />
              Cena
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="price">
                  Cena <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="price"
                  type="number"
                  value={formData.price}
                  onChange={(e) => handleChange('price', e.target.value)}
                  placeholder="500000"
                  className={cn(errors.price && 'border-destructive')}
                />
                {errors.price && <p className="text-sm text-destructive">{errors.price}</p>}
              </div>

              <div className="space-y-2">
                <Label>Waluta</Label>
                <Select
                  value={formData.currency}
                  onValueChange={(value) => handleChange('currency', value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="PLN">PLN</SelectItem>
                    <SelectItem value="EUR">EUR</SelectItem>
                    <SelectItem value="USD">USD</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Property Details */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Szczegóły nieruchomości
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="area_sqm">
                  <Maximize className="inline h-4 w-4 mr-1" />
                  Powierzchnia (m²)
                </Label>
                <Input
                  id="area_sqm"
                  type="number"
                  value={formData.area_sqm}
                  onChange={(e) => handleChange('area_sqm', e.target.value)}
                  placeholder="65"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="rooms">
                  <BedDouble className="inline h-4 w-4 mr-1" />
                  Pokoje
                </Label>
                <Input
                  id="rooms"
                  type="number"
                  value={formData.rooms}
                  onChange={(e) => handleChange('rooms', e.target.value)}
                  placeholder="3"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="bathrooms">
                  <Bath className="inline h-4 w-4 mr-1" />
                  Łazienki
                </Label>
                <Input
                  id="bathrooms"
                  type="number"
                  value={formData.bathrooms}
                  onChange={(e) => handleChange('bathrooms', e.target.value)}
                  placeholder="1"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="year_built">
                  <Calendar className="inline h-4 w-4 mr-1" />
                  Rok budowy
                </Label>
                <Input
                  id="year_built"
                  type="number"
                  value={formData.year_built}
                  onChange={(e) => handleChange('year_built', e.target.value)}
                  placeholder="2020"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="floor">Piętro</Label>
                <Input
                  id="floor"
                  type="number"
                  value={formData.floor}
                  onChange={(e) => handleChange('floor', e.target.value)}
                  placeholder="2"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="total_floors">Liczba pięter w budynku</Label>
                <Input
                  id="total_floors"
                  type="number"
                  value={formData.total_floors}
                  onChange={(e) => handleChange('total_floors', e.target.value)}
                  placeholder="5"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Location */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5" />
              Lokalizacja
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="city">
                  Miasto <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="city"
                  value={formData.city}
                  onChange={(e) => handleChange('city', e.target.value)}
                  placeholder="Warszawa"
                  className={cn(errors.city && 'border-destructive')}
                />
                {errors.city && <p className="text-sm text-destructive">{errors.city}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="district">Dzielnica</Label>
                <Input
                  id="district"
                  value={formData.district}
                  onChange={(e) => handleChange('district', e.target.value)}
                  placeholder="Śródmieście"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="street">Ulica</Label>
                <Input
                  id="street"
                  value={formData.street}
                  onChange={(e) => handleChange('street', e.target.value)}
                  placeholder="ul. Marszałkowska 10"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="zip_code">Kod pocztowy</Label>
                <Input
                  id="zip_code"
                  value={formData.zip_code}
                  onChange={(e) => handleChange('zip_code', e.target.value)}
                  placeholder="00-001"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="country">Kraj</Label>
              <Input
                id="country"
                value={formData.country}
                onChange={(e) => handleChange('country', e.target.value)}
                placeholder="Polska"
              />
            </div>
          </CardContent>
        </Card>

        {/* Features */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Tag className="h-5 w-5" />
              Wyposażenie i cechy
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={newFeature}
                onChange={(e) => setNewFeature(e.target.value)}
                placeholder="Np. Balkon, Garaż, Klimatyzacja..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addFeature();
                  }
                }}
              />
              <Button type="button" onClick={addFeature} variant="outline">
                <Plus className="h-4 w-4" />
              </Button>
            </div>

            <div className="flex flex-wrap gap-2">
              {formData.features.map((feature) => (
                <Badge key={feature} variant="secondary" className="gap-1">
                  {feature}
                  <button
                    type="button"
                    onClick={() => removeFeature(feature)}
                    className="ml-1 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>

            {formData.features.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Dodaj cechy nieruchomości, np. balkon, garaż, klimatyzacja
              </p>
            )}
          </CardContent>
        </Card>

        {/* Additional Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Dodatkowe informacje
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="source">Źródło</Label>
                <Input
                  id="source"
                  value={formData.source}
                  onChange={(e) => handleChange('source', e.target.value)}
                  placeholder="Np. Otodom, OLX, Bezpośrednio"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="external_id">ID zewnętrzne</Label>
                <Input
                  id="external_id"
                  value={formData.external_id}
                  onChange={(e) => handleChange('external_id', e.target.value)}
                  placeholder="ID z portalu"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Submit Buttons */}
        <div className="flex items-center justify-end gap-4">
          <Button type="button" variant="outline" onClick={() => navigate('/listings')}>
            Anuluj
          </Button>
          <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
            <Save className="mr-2 h-4 w-4" />
            {createMutation.isPending || updateMutation.isPending
              ? 'Zapisywanie...'
              : isEditing
              ? 'Zapisz zmiany'
              : 'Utwórz ofertę'}
          </Button>
        </div>
      </form>
    </div>
  );
}
