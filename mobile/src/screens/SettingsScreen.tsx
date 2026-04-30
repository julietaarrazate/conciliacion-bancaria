import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Input } from '@/components/Input';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { apiClient } from '@/services/api';
import { configService } from '@/services/config';
import { useAuthStore } from '@/store/auth';

export const SettingsScreen: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const [url, setUrl] = useState('');
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState<'idle' | 'ok' | 'fail'>('idle');

  useEffect(() => {
    configService.getApiUrl().then(setUrl);
  }, []);

  const handleTest = async () => {
    setTesting(true);
    setStatus('idle');
    const ok = await apiClient.testConnection(url);
    setStatus(ok ? 'ok' : 'fail');
    setTesting(false);
  };

  const handleSave = async () => {
    await apiClient.setBaseUrl(url);
    Alert.alert(
      'OK',
      'URL guardada. Cerrá sesión y volvé a entrar para que tome efecto.'
    );
  };

  const handleReset = async () => {
    await configService.resetApiUrl();
    const def = configService.getDefaultUrl();
    setUrl(def);
    Alert.alert('OK', `URL restaurada a: ${def}`);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Ajustes</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <Card>
          <Text style={styles.sectionTitle}>Servidor</Text>
          <Text style={styles.hint}>
            URL del backend. Si la PC y el celular están en la misma WiFi, usá la IP
            local de la PC (ej: http://192.168.1.8:8000).
          </Text>

          <Input
            label="URL del backend"
            placeholder="http://192.168.1.X:8000"
            value={url}
            onChangeText={setUrl}
            autoCapitalize="none"
            keyboardType="url"
          />

          {status === 'ok' && (
            <Text style={styles.statusOk}>✓ Conexión OK — backend respondió</Text>
          )}
          {status === 'fail' && (
            <Text style={styles.statusFail}>
              ✗ No se pudo conectar — revisá la IP y que el backend esté corriendo
            </Text>
          )}

          <View style={styles.btnRow}>
            <View style={styles.flex}>
              <Button
                title={testing ? 'Probando...' : 'Probar'}
                variant="secondary"
                onPress={handleTest}
                loading={testing}
              />
            </View>
            <View style={styles.flex}>
              <Button title="Guardar" onPress={handleSave} />
            </View>
          </View>

          <View style={{ marginTop: 8 }}>
            <Button
              title="Restaurar URL por defecto"
              variant="secondary"
              onPress={handleReset}
            />
          </View>
        </Card>

        <Card>
          <Text style={styles.sectionTitle}>Sesión</Text>
          {user && (
            <>
              <Text style={styles.field}>
                <Text style={styles.fieldLabel}>Nombre: </Text>
                {user.full_name}
              </Text>
              <Text style={styles.field}>
                <Text style={styles.fieldLabel}>Email: </Text>
                {user.email}
              </Text>
              <Text style={styles.field}>
                <Text style={styles.fieldLabel}>Rol: </Text>
                {user.role}
              </Text>
            </>
          )}
          <View style={{ marginTop: 12 }}>
            <Button title="Cerrar sesión" variant="danger" onPress={logout} />
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6' },
  header: {
    backgroundColor: '#fff',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb'
  },
  title: { fontSize: 18, fontWeight: '700', color: '#111827' },
  scroll: { padding: 16 },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 8
  },
  hint: {
    fontSize: 12,
    color: '#6b7280',
    marginBottom: 12,
    lineHeight: 16
  },
  statusOk: {
    color: '#15803d',
    fontSize: 13,
    fontWeight: '500',
    marginTop: 4,
    marginBottom: 8
  },
  statusFail: {
    color: '#dc2626',
    fontSize: 13,
    fontWeight: '500',
    marginTop: 4,
    marginBottom: 8
  },
  btnRow: { flexDirection: 'row', gap: 8 },
  flex: { flex: 1 },
  field: { fontSize: 14, color: '#111827', marginVertical: 2 },
  fieldLabel: { fontWeight: '600', color: '#374151' }
});
