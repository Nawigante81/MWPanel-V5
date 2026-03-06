import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from '@/hooks/useTheme';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { profileApi } from '@/lib/api';
import {
  User,
  Bell,
  Shield,
  Database,
  Save,
  Moon,
  Sun,
  Monitor,
  Mail,
  Smartphone,
  CheckCircle2,
  Key,
  Palette,
  Camera,
  Trash2,
} from 'lucide-react';

interface SettingsSectionProps {
  icon: React.ElementType;
  title: string;
  description: string;
  children: React.ReactNode;
  color?: 'blue' | 'green' | 'amber' | 'purple' | 'rose';
}

function SettingsSection({ icon: Icon, title, description, children, color = 'blue' }: SettingsSectionProps) {
  const colorClasses = {
    blue: 'bg-blue-500/10 text-blue-600 dark:text-blue-400',
    green: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
    amber: 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
    purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400',
    rose: 'bg-rose-500/10 text-rose-600 dark:text-rose-400',
  };

  return (
    <Card className="card-hover">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className={cn('p-2.5 rounded-xl', colorClasses[color])}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <CardTitle className="text-lg">{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [notifications, setNotifications] = useState({
    email: true,
    push: false,
    priceAlerts: true,
    newListings: true,
    taskReminders: true,
    marketing: false,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [coverUrl, setCoverUrl] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const avatarInputRef = useRef<HTMLInputElement | null>(null);
  const coverInputRef = useRef<HTMLInputElement | null>(null);

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise(resolve => setTimeout(resolve, 500));
    toast.success('Ustawienia zapisane');
    setIsSaving(false);
  };

  useEffect(() => {
    (async () => {
      try {
        const p = await profileApi.get();
        if (p?.avatar_url) setAvatarUrl(p.avatar_url);
        if (p?.cover_url) setCoverUrl(p.cover_url);
      } catch {
        // ignore
      }
    })();
  }, []);

  const handleAvatarUpload = async (file?: File) => {
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) {
      toast.error('Dozwolone formaty: JPG, PNG, WEBP');
      return;
    }
    try {
      setIsSaving(true);
      const res = await profileApi.uploadAvatar(file);
      setAvatarUrl(res?.avatar_url || null);
      toast.success('Zdjęcie profilowe zaktualizowane');
    } catch (e: any) {
      toast.error(e?.message || 'Nie udało się zmienić zdjęcia');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCoverUpload = async (file?: File) => {
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) {
      toast.error('Dozwolone formaty okładki: JPG, PNG, WEBP');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error('Maksymalny rozmiar okładki to 10MB');
      return;
    }

    try {
      setIsSaving(true);
      const localPreview = URL.createObjectURL(file);
      setCoverUrl(localPreview);
      const res = await profileApi.uploadCover(file);
      setCoverUrl(res?.cover_url || localPreview);
      toast.success('Zdjęcie w tle zaktualizowane');
    } catch (e: any) {
      toast.error(e?.message || 'Nie udało się zmienić okładki');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveCover = async () => {
    try {
      setIsSaving(true);
      await profileApi.removeCover();
      setCoverUrl(null);
      toast.success('Okładka usunięta');
    } catch (e: any) {
      toast.error(e?.message || 'Nie udało się usunąć okładki');
    } finally {
      setIsSaving(false);
    }
  };

  const handleChangePassword = async () => {
    try {
      setIsSaving(true);
      await profileApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      toast.success('Hasło zostało zmienione pomyślnie.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (e: any) {
      toast.error(e?.message || 'Nie udało się zmienić hasła');
    } finally {
      setIsSaving(false);
    }
  };

  const initials = user?.name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'U';

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Ustawienia</h1>
        <p className="text-muted-foreground">Zarządzaj swoim kontem i preferencjami</p>
      </div>

      {/* Profile Card */}
      <Card className="card-hover overflow-hidden">
        <div
          className="h-28 sm:h-32 relative"
          style={coverUrl ? { backgroundImage: `url(${coverUrl})`, backgroundSize: 'cover', backgroundPosition: 'center' } : undefined}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleCoverUpload(e.dataTransfer.files?.[0]);
          }}
        >
          {!coverUrl ? <div className="absolute inset-0 bg-gradient-to-r from-primary/20 via-primary/10 to-primary/5" /> : <div className="absolute inset-0 bg-black/15" />}
          <div className="absolute right-3 top-3 flex gap-2">
            <input
              ref={coverInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => handleCoverUpload(e.target.files?.[0])}
            />
            <Button size="sm" variant="secondary" onClick={() => coverInputRef.current?.click()} disabled={isSaving}>
              <Camera className="mr-2 h-4 w-4" />
              Zmień okładkę
            </Button>
            {coverUrl && (
              <Button size="sm" variant="destructive" onClick={handleRemoveCover} disabled={isSaving}>
                <Trash2 className="mr-2 h-4 w-4" />
                Usuń
              </Button>
            )}
          </div>
        </div>
        <CardContent className="p-6 -mt-12">
          <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4">
            <Avatar className="h-24 w-24 ring-4 ring-background">
              {avatarUrl ? <img src={avatarUrl} alt="avatar" className="h-24 w-24 rounded-full object-cover" /> : null}
              <AvatarFallback className="bg-gradient-to-br from-primary to-primary/70 text-primary-foreground text-2xl font-bold">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1">
              <h2 className="text-xl font-semibold">{user?.name || 'Użytkownik'}</h2>
              <p className="text-muted-foreground">{user?.email}</p>
              <div className="flex gap-2 mt-2">
                <Badge variant="secondary" className="text-[10px]">
                  {user?.role || 'Agent'}
                </Badge>
                <Badge variant="outline" className="text-[10px] text-emerald-600">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Aktywny
                </Badge>
              </div>
            </div>
            <div className="space-y-2">
              <input
                ref={avatarInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={(e) => handleAvatarUpload(e.target.files?.[0])}
              />
              <div
                className="border-2 border-dashed rounded-xl px-3 py-2 text-xs text-muted-foreground"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  handleAvatarUpload(e.dataTransfer.files?.[0]);
                }}
              >
                Drag & drop zdjęcia lub użyj przycisku poniżej
              </div>
              <Button variant="outline" className="rounded-xl" onClick={() => avatarInputRef.current?.click()} disabled={isSaving}>
                <Camera className="mr-2 h-4 w-4" />
                Zmień zdjęcie
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Profile Settings */}
        <SettingsSection
          icon={User}
          title="Profil"
          description="Zarządzaj swoimi danymi osobowymi"
          color="blue"
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="firstName">Imię</Label>
                <Input 
                  id="firstName" 
                  defaultValue={user?.name?.split(' ')[0]} 
                  className="rounded-xl"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="lastName">Nazwisko</Label>
                <Input 
                  id="lastName" 
                  defaultValue={user?.name?.split(' ').slice(1).join(' ')} 
                  className="rounded-xl"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input 
                id="email" 
                type="email" 
                defaultValue={user?.email} 
                className="rounded-xl"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Telefon</Label>
              <Input 
                id="phone" 
                type="tel" 
                placeholder="+48 123 456 789"
                className="rounded-xl"
              />
            </div>
            <Button onClick={handleSave} disabled={isSaving} className="rounded-xl">
              <Save className="mr-2 h-4 w-4" />
              {isSaving ? 'Zapisywanie...' : 'Zapisz zmiany'}
            </Button>
          </div>
        </SettingsSection>

        {/* Appearance */}
        <SettingsSection
          icon={Palette}
          title="Wygląd"
          description="Dostosuj wygląd aplikacji"
          color="purple"
        >
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Motyw</Label>
              <div className="grid grid-cols-3 gap-3">
                <button
                  onClick={() => setTheme('light')}
                  className={cn(
                    'flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all',
                    theme === 'light' 
                      ? 'border-primary bg-primary/5' 
                      : 'border-muted hover:border-muted-foreground/30'
                  )}
                >
                  <Sun className="h-6 w-6" />
                  <span className="text-sm font-medium">Jasny</span>
                </button>
                <button
                  onClick={() => setTheme('dark')}
                  className={cn(
                    'flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all',
                    theme === 'dark' 
                      ? 'border-primary bg-primary/5' 
                      : 'border-muted hover:border-muted-foreground/30'
                  )}
                >
                  <Moon className="h-6 w-6" />
                  <span className="text-sm font-medium">Ciemny</span>
                </button>
                <button
                  onClick={() => setTheme('system')}
                  className={cn(
                    'flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all',
                    theme === 'system' 
                      ? 'border-primary bg-primary/5' 
                      : 'border-muted hover:border-muted-foreground/30'
                  )}
                >
                  <Monitor className="h-6 w-6" />
                  <span className="text-sm font-medium">Systemowy</span>
                </button>
              </div>
            </div>
            <div className="flex items-center justify-between p-3 rounded-xl bg-muted/50">
              <div className="flex items-center gap-3">
                {resolvedTheme === 'dark' ? (
                  <Moon className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <Sun className="h-5 w-5 text-muted-foreground" />
                )}
                <div>
                  <p className="font-medium text-sm">Aktualny motyw</p>
                  <p className="text-xs text-muted-foreground">
                    {resolvedTheme === 'dark' ? 'Ciemny' : 'Jasny'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </SettingsSection>

        {/* Notifications */}
        <SettingsSection
          icon={Bell}
          title="Powiadomienia"
          description="Konfiguruj sposób otrzymywania powiadomień"
          color="amber"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-muted">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="space-y-0.5">
                  <Label className="text-sm">Powiadomienia email</Label>
                  <p className="text-xs text-muted-foreground">Otrzymuj powiadomienia na adres email</p>
                </div>
              </div>
              <Switch
                checked={notifications.email}
                onCheckedChange={(checked) =>
                  setNotifications({ ...notifications, email: checked })
                }
              />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-muted">
                  <Smartphone className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="space-y-0.5">
                  <Label className="text-sm">Powiadomienia push</Label>
                  <p className="text-xs text-muted-foreground">Powiadomienia w przeglądarce</p>
                </div>
              </div>
              <Switch
                checked={notifications.push}
                onCheckedChange={(checked) =>
                  setNotifications({ ...notifications, push: checked })
                }
              />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-sm">Alerty o zmianach cen</Label>
                <p className="text-xs text-muted-foreground">Powiadomienia o zmianach cen ofert</p>
              </div>
              <Switch
                checked={notifications.priceAlerts}
                onCheckedChange={(checked) =>
                  setNotifications({ ...notifications, priceAlerts: checked })
                }
              />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-sm">Nowe oferty</Label>
                <p className="text-xs text-muted-foreground">Powiadomienia o nowych ofertach</p>
              </div>
              <Switch
                checked={notifications.newListings}
                onCheckedChange={(checked) =>
                  setNotifications({ ...notifications, newListings: checked })
                }
              />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-sm">Przypomnienia o zadaniach</Label>
                <p className="text-xs text-muted-foreground">Powiadomienia o zbliżających się terminach</p>
              </div>
              <Switch
                checked={notifications.taskReminders}
                onCheckedChange={(checked) =>
                  setNotifications({ ...notifications, taskReminders: checked })
                }
              />
            </div>
            <Button onClick={handleSave} disabled={isSaving} className="rounded-xl w-full">
              <Save className="mr-2 h-4 w-4" />
              {isSaving ? 'Zapisywanie...' : 'Zapisz ustawienia'}
            </Button>
          </div>
        </SettingsSection>

        {/* Security */}
        <SettingsSection
          icon={Shield}
          title="Bezpieczeństwo"
          description="Zarządzaj hasłem i bezpieczeństwem konta"
          color="rose"
        >
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Aktualne hasło</Label>
              <Input 
                id="currentPassword" 
                type="password" 
                className="rounded-xl"
                placeholder="••••••••"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="newPassword">Nowe hasło</Label>
              <Input 
                id="newPassword" 
                type="password" 
                className="rounded-xl"
                placeholder="••••••••"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Potwierdź nowe hasło</Label>
              <Input 
                id="confirmPassword" 
                type="password" 
                className="rounded-xl"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
            <Button onClick={handleChangePassword} disabled={isSaving} className="rounded-xl w-full">
              <Key className="mr-2 h-4 w-4" />
              Zmień hasło
            </Button>
          </div>
        </SettingsSection>
      </div>

      {/* System Info */}
      <SettingsSection
        icon={Database}
        title="Informacje o systemie"
        description="Szczegóły techniczne aplikacji"
        color="green"
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">Wersja aplikacji</p>
            <p className="font-semibold">1.0.0</p>
          </div>
          <div className="p-4 rounded-xl bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">Środowisko</p>
            <p className="font-semibold">{import.meta.env.DEV ? 'Development' : 'Production'}</p>
          </div>
          <div className="p-4 rounded-xl bg-muted/50">
            <p className="text-xs text-muted-foreground mb-1">API URL</p>
            <p className="font-semibold text-xs truncate">
              {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}
            </p>
          </div>
        </div>
      </SettingsSection>
    </div>
  );
}
