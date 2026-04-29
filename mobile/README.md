# Mobile - Sistema Conciliación Bancaria

App móvil React Native (Expo) para iOS y Android.

## Características

- **Login seguro** con JWT (almacenado en SecureStore)
- **Dashboard móvil** con flujo guiado paso a paso
- **Selección de archivos Excel** desde el celular (DocumentPicker)
- **Carga de extractos y planillas** con conciliación automática
- **Visualización de resultados** con stats por categoría
- **Reuso del backend** existente (mismos endpoints que la web)

## Setup

### Pre-requisitos

- Node.js 18+
- Expo Go instalado en el celular (App Store / Google Play)

### Instalación

```bash
cd mobile
npm install
```

### Correr en desarrollo

```bash
npm start
```

Esto abre el Expo Dev Tools. Escaneá el QR con:
- **iOS**: cámara nativa
- **Android**: Expo Go

### Configurar URL del backend

Editá `app.json` → `expo.extra.apiUrl`:

```json
{
  "expo": {
    "extra": {
      "apiUrl": "http://192.168.1.X:8000"
    }
  }
}
```

⚠️ **Importante**: en móvil no funciona `localhost` — usá la IP de tu red local (la del notebook donde corre el backend).

## Estructura

```
mobile/
├── App.tsx                    # Entry point
├── app.json                   # Configuración Expo
├── package.json
├── tsconfig.json
├── babel.config.js
└── src/
    ├── components/            # UI reutilizable
    │   ├── Button.tsx
    │   ├── Input.tsx
    │   └── Card.tsx
    ├── screens/               # Pantallas
    │   ├── LoginScreen.tsx
    │   └── DashboardScreen.tsx
    ├── navigation/            # Stack navigator
    │   └── AppNavigator.tsx
    ├── services/              # API client
    │   └── api.ts
    ├── store/                 # Estado global (Zustand)
    │   └── auth.ts
    └── types/
        └── index.ts
```

## Flujo de uso

1. **Login** → ingresar email/password
2. **Cargar extracto** → seleccionar XLSX desde el celular
3. **Ingresar cliente** → nombre del cliente
4. **Cargar planilla** → seleccionar XLSX → conciliación automática
5. **Ver resultados** → stats por categoría (acreditadas, no encontradas, etc.)

## Tecnologías

- **Expo SDK 50** — framework React Native
- **TypeScript** — type safety
- **React Navigation** — navegación stack
- **Zustand** — estado global
- **Axios** — HTTP client
- **expo-document-picker** — selección de Excel
- **expo-secure-store** — almacenamiento seguro del JWT

## Build para producción

### Android (APK)

```bash
npx expo run:android
```

### iOS

```bash
npx expo run:ios
```

### EAS Build (recomendado para distribución)

```bash
npm install -g eas-cli
eas build --platform android
eas build --platform ios
```

## Troubleshooting

### "No se puede conectar al servidor"

- Verificá que el backend esté corriendo
- Verificá que la IP en `app.json` sea correcta (NO uses localhost)
- El celular y la PC deben estar en la misma red WiFi

### "Network request failed"

- Si usás backend local sin HTTPS, en iOS hay que permitir HTTP en `app.json`:
  ```json
  "ios": {
    "infoPlist": {
      "NSAppTransportSecurity": {
        "NSAllowsArbitraryLoads": true
      }
    }
  }
  ```

## Licencia

Privado - Caneland SA
