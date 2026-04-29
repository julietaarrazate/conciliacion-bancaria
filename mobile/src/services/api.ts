import axios, { AxiosInstance } from 'axios';
import * as SecureStore from 'expo-secure-store';
import Constants from 'expo-constants';
import {
  User,
  AuthResponse,
  ExtractoBancario,
  Planilla,
  ConciliacionResultado
} from '@/types';

const API_BASE_URL =
  (Constants.expoConfig?.extra?.apiUrl as string) || 'http://localhost:8000';

const TOKEN_KEY = 'auth_token';

class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: { 'Content-Type': 'application/json' },
      timeout: 30000
    });

    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }
      return config;
    });
  }

  async loadToken(): Promise<string | null> {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    if (token) this.token = token;
    return token;
  }

  async setToken(token: string) {
    this.token = token;
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  }

  async clearToken() {
    this.token = null;
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  }

  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await this.client.post('/auth/login', { email, password });
    if (res.data.access_token) {
      await this.setToken(res.data.access_token);
    }
    return res.data;
  }

  async getCurrentUser(): Promise<User> {
    const res = await this.client.get('/me');
    return res.data;
  }

  async uploadExtraco(uri: string, filename: string): Promise<ExtractoBancario> {
    const formData = new FormData();
    formData.append('file', {
      uri,
      name: filename,
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    } as any);

    const res = await this.client.post('/extractos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  }

  async uploadPlanilla(
    clienteNombre: string,
    extractoId: number,
    uri: string,
    filename: string
  ): Promise<Planilla> {
    const formData = new FormData();
    formData.append('file', {
      uri,
      name: filename,
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    } as any);

    const res = await this.client.post('/planillas/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { cliente_nombre: clienteNombre, extracto_id: extractoId }
    });
    return res.data;
  }

  async conciliarPlanilla(
    planillaId: number,
    fechaAcred: string = 'hoy'
  ): Promise<ConciliacionResultado> {
    const res = await this.client.post(
      `/planillas/${planillaId}/conciliar`,
      {},
      { params: { fecha_acred: fechaAcred } }
    );
    return res.data;
  }

  async getPlanilla(id: number): Promise<Planilla> {
    const res = await this.client.get(`/planillas/${id}`);
    return res.data;
  }
}

export const apiClient = new ApiClient();
