import React from 'react';
import { View, ActivityIndicator, StyleSheet, Text } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { useAuthStore } from '@/store/auth';
import { LoginScreen } from '@/screens/LoginScreen';
import { DashboardScreen } from '@/screens/DashboardScreen';
import { HistorialScreen } from '@/screens/HistorialScreen';
import { SettingsScreen } from '@/screens/SettingsScreen';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const TabIcon: React.FC<{ label: string; focused: boolean }> = ({ label, focused }) => (
  <Text style={{ fontSize: 18, opacity: focused ? 1 : 0.4 }}>{label}</Text>
);

const MainTabs: React.FC = () => (
  <Tab.Navigator
    screenOptions={{
      headerShown: false,
      tabBarActiveTintColor: '#0284c7',
      tabBarInactiveTintColor: '#9ca3af',
      tabBarStyle: {
        backgroundColor: '#fff',
        borderTopWidth: 1,
        borderTopColor: '#e5e7eb',
        paddingTop: 4,
        height: 60
      },
      tabBarLabelStyle: { fontSize: 11, fontWeight: '600' }
    }}
  >
    <Tab.Screen
      name="Conciliar"
      component={DashboardScreen}
      options={{ tabBarIcon: ({ focused }) => <TabIcon label="📋" focused={focused} /> }}
    />
    <Tab.Screen
      name="Historial"
      component={HistorialScreen}
      options={{ tabBarIcon: ({ focused }) => <TabIcon label="📊" focused={focused} /> }}
    />
    <Tab.Screen
      name="Ajustes"
      component={SettingsScreen}
      options={{ tabBarIcon: ({ focused }) => <TabIcon label="⚙️" focused={focused} /> }}
    />
  </Tab.Navigator>
);

export const AppNavigator: React.FC = () => {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);

  if (isLoading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color="#0284c7" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {isAuthenticated ? (
          <Stack.Screen name="Main" component={MainTabs} />
        ) : (
          <Stack.Screen name="Login" component={LoginScreen} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f3f4f6'
  }
});
