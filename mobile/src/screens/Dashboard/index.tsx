import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import * as SecureStore from 'expo-secure-store'
import Constants from 'expo-constants'

const API_URL = Constants.expoConfig?.extra?.apiUrl

export default function DashboardScreen() {
  const { data = [], isLoading } = useQuery({
    queryKey: ['reconciliations'],
    queryFn: async () => {
      const token = await SecureStore.getItemAsync('access_token')
      const { data } = await axios.get(`${API_URL}/reconciliations/`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      return data
    },
  })

  return (
    <View style={styles.container}>
      {isLoading ? (
        <Text style={styles.loading}>Cargando...</Text>
      ) : (
        <FlatList
          data={data}
          keyExtractor={(item) => String(item.id)}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Conciliación #{item.id}</Text>
              <Text style={[styles.status, item.status === 'closed' ? styles.closed : styles.open]}>
                {item.status}
              </Text>
              <Text style={styles.diff}>Diferencia: ${item.difference}</Text>
            </View>
          )}
          ListEmptyComponent={<Text style={styles.empty}>No hay conciliaciones</Text>}
        />
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb', padding: 16 },
  loading: { textAlign: 'center', marginTop: 40, color: '#6b7280' },
  empty: { textAlign: 'center', marginTop: 40, color: '#9ca3af' },
  card: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginBottom: 12, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 4, elevation: 2 },
  cardTitle: { fontSize: 16, fontWeight: '600', marginBottom: 4 },
  status: { fontSize: 13, fontWeight: '500', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 99, alignSelf: 'flex-start', marginBottom: 4 },
  open: { backgroundColor: '#dbeafe', color: '#1d4ed8' },
  closed: { backgroundColor: '#dcfce7', color: '#16a34a' },
  diff: { fontSize: 14, color: '#6b7280' },
})
