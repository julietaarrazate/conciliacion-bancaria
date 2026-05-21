# CLAUDE.md — Mobile (React Native / Expo)
> Contexto específico del módulo mobile. Actualizar cuando cambien pantallas o flujos.

---

## Stack

- **React Native** + **Expo** (SDK 51+)
- **TypeScript**
- **React Navigation** v6 para navegación
- **Zustand** para estado global (compartir lógica con web donde sea posible)
- **React Query** para datos del servidor
- **Axios** para HTTP

---

## Estructura

```
mobile/src/
├── screens/             ← pantallas (una carpeta por pantalla)
│   ├── Dashboard/
│   ├── Accounts/
│   ├── Statements/
│   ├── Reconciliation/
│   └── Auth/
├── components/
│   ├── ui/              ← componentes genéricos nativos
│   └── domain/          ← componentes de negocio
├── navigation/
│   └── index.tsx        ← configuración de navegación
├── services/
│   ├── api.ts           ← instancia axios (misma URL base que web)
│   └── *.service.ts
├── store/               ← stores Zustand
└── types/               ← interfaces TypeScript
```

---

## Enfoque mobile

El mobile es **complemento** del web, no reemplazo. Prioridades:

1. Ver estado de conciliaciones pendientes
2. Aprobar/rechazar matches en cualquier lugar
3. Notificaciones de alertas (extracto nuevo, diferencia detectada)
4. Consulta rápida de saldos

Las operaciones complejas (importar extractos, configuración) van al web.

---

## Variables de entorno

```bash
# app.config.js o .env con expo-constants
EXPO_PUBLIC_API_URL=http://localhost:8000
```

---

## Estado actual

> Actualizar en cada sesión

- [ ] Setup Expo + TypeScript + Navigation
- [ ] Auth (login + token storage seguro)
- [ ] Dashboard mobile
- [ ] Lista de conciliaciones pendientes
- [ ] Detalle y aprobación de match
- [ ] Notificaciones push
