# CLAUDE.md — Frontend (React Web)
> Contexto específico del módulo web. Actualizar cuando cambien componentes clave o patrones.

---

## Stack

- **React 18** + **TypeScript**
- **Vite** como bundler
- **React Router v6** para navegación
- **Zustand** para estado global
- **React Query (TanStack Query)** para datos del servidor
- **Axios** para HTTP
- **Tailwind CSS** para estilos

---

## Estructura

```
frontend/src/
├── components/
│   ├── ui/              ← componentes genéricos (Button, Modal, Table, etc.)
│   └── domain/          ← componentes de negocio (ReconciliationRow, etc.)
├── pages/               ← una carpeta por página/vista
│   ├── Dashboard/
│   ├── Accounts/
│   ├── Statements/
│   ├── Reconciliation/
│   └── Reports/
├── hooks/               ← hooks personalizados
├── services/
│   ├── api.ts           ← instancia axios con interceptors
│   └── *.service.ts     ← servicios por dominio
├── store/               ← stores Zustand
├── types/               ← interfaces TypeScript globales
└── utils/               ← helpers puros
```

---

## Patrones establecidos

### React Query para todo lo del servidor
```typescript
// NO usar useState/useEffect para fetch — usar React Query
const { data, isLoading } = useQuery({
  queryKey: ['reconciliations', accountId],
  queryFn: () => reconciliationService.getAll(accountId),
})
```

### Tipos estrictos
```typescript
// SIEMPRE tipar props y responses
interface ReconciliationCardProps {
  reconciliation: Reconciliation
  onMatch: (id: number) => void
}
```

### Manejo de errores centralizado
```typescript
// En api.ts hay interceptores para 401 (redirect login) y 500 (toast error)
// No duplicar manejo de errores en componentes
```

---

## Páginas y rutas

| Ruta | Página | Descripción |
|------|--------|-------------|
| `/` | Dashboard | Resumen general, KPIs |
| `/accounts` | Accounts | Lista y gestión de cuentas |
| `/statements` | Statements | Importar y ver extractos |
| `/reconciliation/:id` | Reconciliation | Proceso de conciliación interactivo |
| `/reports` | Reports | Reportes y exportación |
| `/login` | Login | Autenticación |

---

## Variables de entorno

```bash
VITE_API_URL=http://localhost:8000
```

---

## Estado actual

> Actualizar en cada sesión

- [ ] Setup inicial (Vite + TS + Router)
- [ ] Layout base (sidebar + header)
- [ ] Auth (login, guards de ruta)
- [ ] Dashboard
- [ ] Gestión de cuentas
- [ ] Import de extractos
- [ ] UI de conciliación (drag & match)
- [ ] Reportes
- [ ] Tests
