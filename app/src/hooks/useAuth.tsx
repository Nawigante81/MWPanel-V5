import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { authApi } from '@/lib/api';
import { queryClient } from '@/lib/queryClient';
import type { User } from '@/types';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);


export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check auth on mount
  useEffect(() => {
    const initAuth = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        const savedUser = localStorage.getItem('auth_user');
        if (token && savedUser) {
          try {
            const current = await authApi.getCurrentUser();
            setUser(current);
            localStorage.setItem('auth_user', JSON.stringify(current));
            queryClient.setQueryData(['profile', current?.id], current);
            return;
          } catch {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('auth_user');
          }
        }
      } catch (err) {
        console.error('Auth init error:', err);
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = async (username: string, password: string) => {
    setError(null);
    setIsLoading(true);

    try {
      const result = await authApi.login(username, password);
      if (!result?.access_token || !result?.user) {
        throw new Error('Nieprawidłowa odpowiedź serwera logowania');
      }
      localStorage.setItem('auth_token', result.access_token);
      localStorage.setItem('auth_user', JSON.stringify(result.user));
      setUser(result.user);
      queryClient.clear();
      queryClient.setQueryData(['profile', result.user?.id], result.user);
    } catch (err: any) {
      setError(err.message || 'Błąd logowania');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    await authApi.logout();
    localStorage.removeItem('auth_user');
    setUser(null);
    setError(null);
    queryClient.clear();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        error,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
