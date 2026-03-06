import { useEffect, useState } from 'react';
import { Link, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { authApi } from '@/lib/api';
import { useTheme } from '@/hooks/useTheme';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import mwLogo from '@/assets/mw-logo.svg';

import { 
  Loader2, 
  AlertCircle, 
  Eye, 
  EyeOff, 
  Moon, 
  Sun,
  TrendingUp,
  Users,
  Shield,
} from 'lucide-react';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [bootstrapInfo, setBootstrapInfo] = useState<{ requires_bootstrap: boolean; hint?: string } | null>(null);
  const { login, isAuthenticated, isLoading, error } = useAuth();
  const { resolvedTheme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  useEffect(() => {
    authApi.bootstrapStatus().then((res) => setBootstrapInfo(res)).catch(() => setBootstrapInfo(null));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate('/');
    } catch {
      // Error is handled by auth context
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left side - decorative */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary via-primary/90 to-primary/70" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4xIj48Y2lyY2xlIGN4PSIzMCIgY3k9IjMwIiByPSIyIi8+PC9nPjwvZz48L3N2Zz4=')] opacity-30" />
        
        {/* Decorative elements */}
        <div className="absolute top-20 left-20 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-white/5 rounded-full blur-3xl" />
        
        <div className="relative z-10 flex flex-col justify-between p-12 text-white">
          <div>
            <div className="flex items-center mb-8">
              <img src={mwLogo} alt="MWPanel" className="h-10 w-auto object-contain" />
            </div>
            
            <h1 className="text-4xl font-bold mb-6 leading-tight">
              Zarządzaj swoimi<br />
              nieruchomościami<br />
              <span className="text-white/80">z łatwością</span>
            </h1>
            
            <p className="text-lg text-white/70 max-w-md">
              Kompletne narzędzie dla biur nieruchomości. Oferty, kontakty, zadania i wiele więcej w jednym miejscu.
            </p>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 backdrop-blur">
                <TrendingUp className="h-6 w-6" />
              </div>
              <div>
                <p className="font-semibold">Zwiększ efektywność</p>
                <p className="text-white/70 text-sm">Automatyzuj procesy sprzedaży</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 backdrop-blur">
                <Users className="h-6 w-6" />
              </div>
              <div>
                <p className="font-semibold">Zarządzaj kontaktami</p>
                <p className="text-white/70 text-sm">Pełna baza klientów i partnerów</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 backdrop-blur">
                <Shield className="h-6 w-6" />
              </div>
              <div>
                <p className="font-semibold">Bezpieczne dane</p>
                <p className="text-white/70 text-sm">Szyfrowanie i regularne backupy</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right side - login form */}
      <div className="flex-1 flex flex-col">
        {/* Theme toggle */}
        <div className="flex justify-end p-4">
          <Button 
            variant="ghost" 
            size="icon" 
            className="rounded-xl"
            onClick={toggleTheme}
          >
            {resolvedTheme === 'dark' ? (
              <Sun className="h-5 w-5" />
            ) : (
              <Moon className="h-5 w-5" />
            )}
          </Button>
        </div>

        <div className="flex-1 flex items-center justify-center p-4 sm:p-8">
          <div className="w-full max-w-md">
            {/* Mobile logo */}
            <div className="lg:hidden mb-8 text-center">
              <img src={mwLogo} alt="MWPanel" className="mx-auto mb-4 h-14 w-auto object-contain" />
              <p className="text-muted-foreground">Zaloguj się do systemu</p>
            </div>

            <Card className="card-hover shadow-xl shadow-black/5">
              <CardHeader className="space-y-1">
                <CardTitle className="text-2xl">Witaj z powrotem</CardTitle>
                <CardDescription>
                  Wprowadź swoje dane dostępowe, aby kontynuować
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  {error && (
                    <Alert variant="destructive" className="rounded-xl">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}

                  {bootstrapInfo?.requires_bootstrap ? (
                    <Alert className="rounded-xl">
                      <AlertDescription>
                        Brak kont w systemie. Wykonaj bootstrap admina przez endpoint <code>/auth/bootstrap-admin</code>.
                      </AlertDescription>
                    </Alert>
                  ) : null}


                  <div className="space-y-2">
                    <Label htmlFor="username">Login</Label>
                    <Input
                      id="username"
                      type="text"
                      placeholder="admin"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      className="rounded-xl h-11"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="password">Hasło</Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        className="rounded-xl h-11 pr-10"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="absolute right-0 top-0 h-11 w-11 rounded-xl"
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? (
                          <EyeOff className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <Eye className="h-4 w-4 text-muted-foreground" />
                        )}
                      </Button>
                    </div>
                  </div>



                  <Button 
                    type="submit" 
                    className="w-full rounded-xl h-11" 
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Logowanie...
                      </>
                    ) : (
                      'Zaloguj się'
                    )}
                  </Button>

                  <div className="text-sm text-center text-muted-foreground">
                    Nie masz konta? <Link to="/register" className="underline">Zarejestruj się</Link>
                  </div>
                </form>


              </CardContent>
            </Card>

            <p className="mt-8 text-center text-sm text-muted-foreground">
              MWPanel v1.0 • Wszystkie prawa zastrzeżone
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
