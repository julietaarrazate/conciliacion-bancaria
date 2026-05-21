import { useState } from 'react'
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert } from 'react-native'
import { NativeStackNavigationProp } from '@react-navigation/native-stack'
import axios from 'axios'
import * as SecureStore from 'expo-secure-store'
import Constants from 'expo-constants'
import { RootStackParamList } from '../../navigation'

type Props = { navigation: NativeStackNavigationProp<RootStackParamList, 'Login'> }
const API_URL = Constants.expoConfig?.extra?.apiUrl

export default function LoginScreen({ navigation }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogin = async () => {
    setLoading(true)
    try {
      const { data } = await axios.post(`${API_URL}/auth/login`, { email, password })
      await SecureStore.setItemAsync('access_token', data.access_token)
      navigation.replace('Dashboard')
    } catch {
      Alert.alert('Error', 'Email o contraseña incorrectos')
    } finally {
      setLoading(false)
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Conciliación Bancaria</Text>
      <TextInput style={styles.input} placeholder="Email" value={email}
        onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
      <TextInput style={styles.input} placeholder="Contraseña" value={password}
        onChangeText={setPassword} secureTextEntry />
      <TouchableOpacity style={styles.button} onPress={handleLogin} disabled={loading}>
        <Text style={styles.buttonText}>{loading ? 'Ingresando...' : 'Ingresar'}</Text>
      </TouchableOpacity>
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#f9fafb' },
  title: { fontSize: 24, fontWeight: 'bold', textAlign: 'center', marginBottom: 32, color: '#1d4ed8' },
  input: { borderWidth: 1, borderColor: '#d1d5db', borderRadius: 8, padding: 12, marginBottom: 12, backgroundColor: '#fff' },
  button: { backgroundColor: '#1d4ed8', padding: 14, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
})
