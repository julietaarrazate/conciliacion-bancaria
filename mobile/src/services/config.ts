import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const KEY_API_URL = 'config_api_url';

const DEFAULT_URL =
  (Constants.expoConfig?.extra?.apiUrl as string) || 'http://192.168.1.8:8000';

export const configService = {
  async getApiUrl(): Promise<string> {
    const stored = await AsyncStorage.getItem(KEY_API_URL);
    return stored || DEFAULT_URL;
  },

  async setApiUrl(url: string): Promise<void> {
    const clean = url.trim().replace(/\/$/, '');
    await AsyncStorage.setItem(KEY_API_URL, clean);
  },

  async resetApiUrl(): Promise<void> {
    await AsyncStorage.removeItem(KEY_API_URL);
  },

  getDefaultUrl(): string {
    return DEFAULT_URL;
  }
};
