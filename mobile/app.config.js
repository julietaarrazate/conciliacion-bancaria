export default {
  expo: {
    name: 'Conciliación Bancaria',
    slug: 'conciliacion-bancaria',
    version: '0.1.0',
    orientation: 'portrait',
    icon: './assets/icon.png',
    splash: { image: './assets/splash.png', resizeMode: 'contain', backgroundColor: '#1d4ed8' },
    ios: { supportsTablet: true, bundleIdentifier: 'com.julietaarrazate.conciliacion' },
    android: { adaptiveIcon: { foregroundImage: './assets/adaptive-icon.png', backgroundColor: '#1d4ed8' }, package: 'com.julietaarrazate.conciliacion' },
    extra: { apiUrl: process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000' },
  },
}
