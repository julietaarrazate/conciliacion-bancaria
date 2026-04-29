import { create } from 'zustand';
import { User } from '@/types';
import { apiClient } from '@/services/api';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadStoredAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (email, password) => {
    const res = await apiClient.login(email, password);
    set({
      user: res.user,
      token: res.access_token,
      isAuthenticated: true,
      isLoading: false
    });
  },

  logout: async () => {
    await apiClient.clearToken();
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false
    });
  },

  loadStoredAuth: async () => {
    set({ isLoading: true });
    const token = await apiClient.loadToken();
    if (token) {
      try {
        const user = await apiClient.getCurrentUser();
        set({
          user,
          token,
          isAuthenticated: true,
          isLoading: false
        });
      } catch {
        await apiClient.clearToken();
        set({ isLoading: false });
      }
    } else {
      set({ isLoading: false });
    }
  }
}));
