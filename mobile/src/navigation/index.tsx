import { createNativeStackNavigator } from '@react-navigation/native-stack'
import LoginScreen from '../screens/Login'
import DashboardScreen from '../screens/Dashboard'

export type RootStackParamList = {
  Login: undefined
  Dashboard: undefined
  Reconciliation: { id: number }
}

const Stack = createNativeStackNavigator<RootStackParamList>()

export function RootNavigator() {
  return (
    <Stack.Navigator initialRouteName="Login">
      <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Dashboard" component={DashboardScreen} options={{ title: 'Conciliaciones' }} />
    </Stack.Navigator>
  )
}
