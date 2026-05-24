# Frontend - Sistema Conciliación Bancaria

Interfaz web React para la plataforma de conciliación bancaria.

## Características

- **Autenticación JWT** con login seguro
- **Dashboard intuitivo** para cargar y reconciliar archivos
- **Componentes reutilizables** (Button, Input, FileUpload)
- **Gestión de estado** con Zustand
- **API Client tipado** con TypeScript
- **Diseño responsivo** con TailwindCSS
- **Drag-and-drop** para carga de archivos

## Setup Rápido

### Instalación

```bash
cd frontend
npm install
```

### Desarrollo

```bash
npm run dev
```

La aplicación estará en `http://localhost:3000`

### Build Producción

```bash
npm run build
```

## Estructura del Proyecto

```
frontend/
├── src/
│   ├── components/          # Componentes reutilizables
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   └── FileUpload.tsx
│   ├── pages/              # Páginas de la app
│   │   ├── Login.tsx
│   │   └── Dashboard.tsx
│   ├── services/           # Servicios API
│   │   └── api.ts
│   ├── store/              # Estado global (Zustand)
│   │   └── auth.ts
│   ├── types/              # Tipos TypeScript
│   │   └── index.ts
│   ├── styles/             # Estilos globales
│   │   └── index.css
│   ├── App.tsx             # Componente raíz
│   └── main.tsx            # Entry point
├── index.html              # HTML template
├── vite.config.ts          # Configuración Vite
├── tailwind.config.js      # Configuración TailwindCSS
├── tsconfig.json           # Configuración TypeScript
└── package.json            # Dependencias
```

## Variables de Entorno

Crear `.env` basado en `.env.example`:

```env
VITE_API_URL=http://localhost:8000
```

## Flujo de Usuario

1. **Login**: Ingresa email y contraseña
2. **Dashboard**: 
   - Carga extracto bancario (XLSX)
   - Ingresa nombre del cliente
   - Carga planilla del cliente (XLSX)
   - Sistema reconcilia automáticamente
3. **Resultados**: Ve estadísticas de la conciliación

## Componentes Principales

### Login.tsx
- Formulario de autenticación
- Gestión de errores
- Redirección post-login

### Dashboard.tsx
- Vista principal después del login
- Upload de archivos con drag-drop
- Formulario de conciliación
- Visualización de resultados

### FileUpload.tsx
- Soporte drag-and-drop
- Validación de tipo de archivo
- Visual feedback

## API Integration

El `apiClient` en `services/api.ts` maneja:
- Autenticación (login, registro)
- Upload de archivos
- Llamadas a endpoints de conciliación
- Manejo automático de JWT tokens

## Estado Global

Usando `useAuthStore` de Zustand:
- Información del usuario
- Token JWT
- Métodos de login/logout
- Verificación de permisos

## Testing

```bash
npm run test
```

## Lint

```bash
npm run lint
```

## Build & Deploy

```bash
# Build para producción
npm run build

# Preview del build local
npm run preview
```

La carpeta `dist/` contiene los archivos listos para desplegar.

## Tecnologías

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **React Router** - Routing
- **TailwindCSS** - Styling
- **Axios** - HTTP client
- **Zustand** - State management

## Desarrollo

### Agregar nuevo componente

1. Crear en `src/components/MiComponente.tsx`
2. Usar en pages o otros componentes
3. Exportar de `src/components/index.ts` si es reutilizable

### Agregar nueva página

1. Crear en `src/pages/MiPagina.tsx`
2. Importar en `App.tsx`
3. Agregar ruta en `<Routes>`

### Conectar a nuevo endpoint

1. Agregar método en `src/services/api.ts`
2. Usar `apiClient.miMetodo()` en componentes

## Troubleshooting

### "Cannot find module" errors

Reinstalar dependencias:
```bash
rm node_modules package-lock.json
npm install
```

### API no responde

Verificar que el backend está corriendo:
```bash
curl http://localhost:8000/health
```

### Build lento

Limpiar cache de Vite:
```bash
rm -rf node_modules/.vite
npm run build
```

## Licencia

Privado - Organización A
