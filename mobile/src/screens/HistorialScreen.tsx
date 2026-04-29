import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
  TextInput
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Card } from '@/components/Card';
import { apiClient } from '@/services/api';
import { PlanillaHistorialItem } from '@/types';

export const HistorialScreen: React.FC = () => {
  const [items, setItems] = useState<PlanillaHistorialItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await apiClient.getHistorialPlanillas({
        cliente: filter || undefined,
        limit: 100
      });
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const renderItem = ({ item }: { item: PlanillaHistorialItem }) => (
    <Card>
      <View style={styles.row}>
        <Text style={styles.cliente}>{item.cliente_nombre}</Text>
        <Text style={styles.fecha}>
          {new Date(item.fecha_carga).toLocaleDateString('es-AR')}
        </Text>
      </View>
      <Text style={styles.archivo} numberOfLines={1}>
        {item.nombre_archivo}
      </Text>
      <Text style={styles.usuario}>por {item.usuario_nombre}</Text>

      <View style={styles.stats}>
        <View style={[styles.stat, styles.statGreen]}>
          <Text style={styles.statNumber}>{item.acreditadas}</Text>
          <Text style={styles.statLabel}>OK</Text>
        </View>
        <View style={[styles.stat, styles.statRed]}>
          <Text style={styles.statNumber}>{item.no_encontradas}</Text>
          <Text style={styles.statLabel}>No está</Text>
        </View>
        <View style={[styles.stat, styles.statYellow]}>
          <Text style={styles.statNumber}>{item.duplicadas}</Text>
          <Text style={styles.statLabel}>Dup.</Text>
        </View>
        <View style={[styles.stat, styles.statBlue]}>
          <Text style={styles.statNumber}>{item.sin_datos}</Text>
          <Text style={styles.statLabel}>Datos</Text>
        </View>
      </View>
    </Card>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Historial</Text>
      </View>

      <View style={styles.searchBox}>
        <TextInput
          style={styles.search}
          placeholder="Filtrar por cliente..."
          placeholderTextColor="#9ca3af"
          value={filter}
          onChangeText={setFilter}
          onSubmitEditing={load}
          returnKeyType="search"
        />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#0284c7" />
        </View>
      ) : (
        <FlatList
          data={items}
          renderItem={renderItem}
          keyExtractor={(item) => item.id.toString()}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={styles.emptyText}>Sin reconciliaciones</Text>
            </View>
          }
        />
      )}
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
  searchBox: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 4
  },
  search: {
    backgroundColor: '#fff',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    color: '#111827'
  },
  list: { padding: 16 },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  cliente: { fontSize: 16, fontWeight: '700', color: '#111827' },
  fecha: { fontSize: 12, color: '#6b7280' },
  archivo: { fontSize: 13, color: '#374151', marginTop: 2 },
  usuario: { fontSize: 11, color: '#9ca3af', marginTop: 2 },
  stats: { flexDirection: 'row', gap: 6, marginTop: 10 },
  stat: { flex: 1, padding: 8, borderRadius: 8, alignItems: 'center' },
  statGreen: { backgroundColor: '#dcfce7' },
  statRed: { backgroundColor: '#fee2e2' },
  statYellow: { backgroundColor: '#fef3c7' },
  statBlue: { backgroundColor: '#dbeafe' },
  statNumber: { fontSize: 16, fontWeight: '700', color: '#111827' },
  statLabel: { fontSize: 10, color: '#374151' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  emptyText: { color: '#6b7280' }
});
