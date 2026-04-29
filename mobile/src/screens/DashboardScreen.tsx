import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as DocumentPicker from 'expo-document-picker';
import { Button } from '@/components/Button';
import { Input } from '@/components/Input';
import { Card } from '@/components/Card';
import { useAuthStore } from '@/store/auth';
import { apiClient } from '@/services/api';
import { ConciliacionResultado } from '@/types';

export const DashboardScreen: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const [extractoId, setExtractoId] = useState<number | null>(null);
  const [extractoName, setExtractoName] = useState<string>('');
  const [clienteNombre, setClienteNombre] = useState('');
  const [planillaName, setPlanillaName] = useState('');
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState<ConciliacionResultado | null>(null);

  const pickExcel = async () => {
    const res = await DocumentPicker.getDocumentAsync({
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      copyToCacheDirectory: true
    });

    if (res.canceled || !res.assets || res.assets.length === 0) return null;
    return res.assets[0];
  };

  const handleUploadExtraco = async () => {
    const file = await pickExcel();
    if (!file) return;

    setLoading(true);
    try {
      const data = await apiClient.uploadExtraco(file.uri, file.name);
      setExtractoId(data.id);
      setExtractoName(file.name);
      Alert.alert('OK', `Extracto cargado: ${file.name}`);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Error al cargar extracto');
    } finally {
      setLoading(false);
    }
  };

  const handleUploadPlanilla = async () => {
    if (!extractoId) {
      Alert.alert('Falta extracto', 'Primero cargá un extracto bancario');
      return;
    }
    if (!clienteNombre.trim()) {
      Alert.alert('Falta cliente', 'Ingresá el nombre del cliente');
      return;
    }

    const file = await pickExcel();
    if (!file) return;

    setLoading(true);
    setResultado(null);
    try {
      const planilla = await apiClient.uploadPlanilla(
        clienteNombre,
        extractoId,
        file.uri,
        file.name
      );
      setPlanillaName(file.name);

      const r = await apiClient.conciliarPlanilla(planilla.id);
      setResultado(r);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Error en conciliación');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setExtractoId(null);
    setExtractoName('');
    setClienteNombre('');
    setPlanillaName('');
    setResultado(null);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Conciliación</Text>
          <Text style={styles.headerSubtitle}>{user?.full_name}</Text>
        </View>
        <Button title="Salir" variant="secondary" onPress={logout} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <Card>
          <Text style={styles.stepTitle}>1. Extracto Bancario</Text>
          {extractoName ? (
            <Text style={styles.success}>✓ {extractoName}</Text>
          ) : (
            <Text style={styles.hint}>Selecciona el archivo del extracto (XLSX)</Text>
          )}
          <Button
            title={extractoName ? 'Cambiar extracto' : 'Cargar extracto'}
            onPress={handleUploadExtraco}
            loading={loading && !extractoId}
            variant={extractoName ? 'secondary' : 'primary'}
          />
        </Card>

        {extractoId && (
          <Card>
            <Text style={styles.stepTitle}>2. Cliente</Text>
            <Input
              label="Nombre del cliente"
              placeholder="Ej: Green, Tucu, David..."
              value={clienteNombre}
              onChangeText={setClienteNombre}
              editable={!loading}
            />
          </Card>
        )}

        {extractoId && clienteNombre.trim().length > 0 && (
          <Card>
            <Text style={styles.stepTitle}>3. Planilla del cliente</Text>
            {planillaName ? (
              <Text style={styles.success}>✓ {planillaName}</Text>
            ) : (
              <Text style={styles.hint}>
                Selecciona la planilla del cliente (XLSX)
              </Text>
            )}
            <Button
              title="Cargar y conciliar"
              onPress={handleUploadPlanilla}
              loading={loading && !!extractoId}
            />
          </Card>
        )}

        {resultado && (
          <Card>
            <Text style={styles.stepTitle}>Resultado</Text>
            <View style={styles.statsRow}>
              <View style={[styles.stat, styles.statGreen]}>
                <Text style={styles.statNumber}>{resultado.acreditadas}</Text>
                <Text style={styles.statLabel}>Acreditadas</Text>
              </View>
              <View style={[styles.stat, styles.statRed]}>
                <Text style={styles.statNumber}>{resultado.no_encontradas}</Text>
                <Text style={styles.statLabel}>No encontradas</Text>
              </View>
            </View>
            <View style={styles.statsRow}>
              <View style={[styles.stat, styles.statYellow]}>
                <Text style={styles.statNumber}>{resultado.duplicadas}</Text>
                <Text style={styles.statLabel}>Duplicadas</Text>
              </View>
              <View style={[styles.stat, styles.statBlue]}>
                <Text style={styles.statNumber}>{resultado.sin_datos}</Text>
                <Text style={styles.statLabel}>Sin datos</Text>
              </View>
            </View>
            <Text style={styles.totalText}>
              Total: {resultado.filas_procesadas} filas procesadas
            </Text>
            <View style={{ marginTop: 12 }}>
              <Button title="Nueva conciliación" variant="secondary" onPress={handleReset} />
            </View>
          </Card>
        )}

        {loading && (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator size="large" color="#0284c7" />
            <Text style={styles.loadingText}>Procesando...</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f3f4f6'
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb'
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827'
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#6b7280'
  },
  scroll: {
    padding: 16
  },
  stepTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 8
  },
  hint: {
    fontSize: 13,
    color: '#6b7280',
    marginBottom: 12
  },
  success: {
    fontSize: 13,
    color: '#15803d',
    marginBottom: 12,
    fontWeight: '500'
  },
  statsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8
  },
  stat: {
    flex: 1,
    padding: 12,
    borderRadius: 10
  },
  statGreen: { backgroundColor: '#dcfce7' },
  statRed: { backgroundColor: '#fee2e2' },
  statYellow: { backgroundColor: '#fef3c7' },
  statBlue: { backgroundColor: '#dbeafe' },
  statNumber: {
    fontSize: 22,
    fontWeight: '700',
    color: '#111827'
  },
  statLabel: {
    fontSize: 12,
    color: '#374151'
  },
  totalText: {
    fontSize: 13,
    color: '#6b7280',
    marginTop: 8,
    textAlign: 'center'
  },
  loadingOverlay: {
    alignItems: 'center',
    padding: 16
  },
  loadingText: {
    marginTop: 8,
    fontSize: 13,
    color: '#6b7280'
  }
});
