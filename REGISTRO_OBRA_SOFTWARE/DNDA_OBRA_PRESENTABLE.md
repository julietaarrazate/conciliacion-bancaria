# IDENTIFICACIÓN DE LA OBRA PRESENTABLE
## Sistema Integral de Gestión Financiera, Contable y Empresarial

**Versión:** v3.12  
**Autora:** Julieta Arrazate  
**Fecha:** Junio 2026

---

## LA OBRA INFORMÁTICA

Cuadra es una **aplicación web multiplataforma** para gestión financiera, contable y bancaria.

### Componentes de la obra:

#### 1. **BACKEND** (API REST — FastAPI + Python 3.11)
- **Ubicación:** `/backend`
- **Responsabilidad:** Lógica de negocio, motor de conciliación, contabilidad automática, APIs REST
- **Contenido:** 22 routers, 18 servicios, 18 modelos, 9 migraciones, 156 tests
- **Tecnología:** FastAPI, SQLAlchemy, PostgreSQL, APScheduler
- **Tamaño:** ~1.1 MB (sin node_modules, __pycache__, .venv)

#### 2. **FRONTEND Web** (PWA — React 18 + TypeScript + Vite)
- **Ubicación:** `/frontend`
- **Responsabilidad:** Interfaz web instalable como Progressive Web App (PWA)
- **Contenido:** 31 páginas, 18 componentes, cliente HTTP centralizado, 6 stores de estado
- **Tecnología:** React 18, TypeScript, TailwindCSS, Zustand, Vite
- **Tamaño:** ~1.5 MB (sin node_modules)
- **Despliegue real:** Compilado a `/dist/` y subido a Vercel (https://conciliacion-bancaria-ten.vercel.app)

#### 3. **FRONTEND Mobile** (Aplicación nativa — React Native + Expo)
- **Ubicación:** `/mobile`
- **Responsabilidad:** Interfaz móvil nativa para iOS/Android
- **Contenido:** Pantallas React Native, navegación nativa, estado global
- **Tecnología:** React Native, Expo, React Navigation
- **Tamaño:** ~836 KB (sin node_modules)

#### 4. **Base de Datos** (Migraciones — Alembic)
- **Ubicación:** `/backend/alembic/versions`
- **Responsabilidad:** Schema de base de datos relacional
- **Contenido:** 9 migraciones que definen 18 modelos principales
- **Tecnología:** Alembic, SQLAlchemy declarative

#### 5. **Configuración e Inicialización**
- **Ubicación:** `/backend`
- **Archivos:** `seed.py`, `main.py`, `config.py`
- **Responsabilidad:** Datos iniciales, setup, plan de cuentas, scheduler

---

## DESCRIPCIÓN TÉCNICA RESUMIDA

**Arquitectura de 3 capas:**

```
FRONTEND WEB (PWA)          FRONTEND MÓVIL (React Native)
        ↓                                ↓
        └─────────────── API REST (FastAPI) ──────────────┘
                              ↓
                        Base de datos
                        (PostgreSQL)
```

**Flujo de funcionamiento:**

1. Usuario accede a la aplicación web o móvil
2. Frontend comunica con el backend por API REST (HTTP)
3. Backend procesa solicitudes, ejecuta lógica de negocio
4. Backend persiste datos en PostgreSQL
5. Frontend renderiza respuestas

---

## ORIGINALIDAD Y COMPONENTES CLAVE

### Algoritmos originales implementados:

1. **Motor de conciliación bancaria** — Scoring multi-criterio con 12+ factores de identificación
2. **Motor contable automático** — Generación automática de 18+ tipos de asientos
3. **Sistema de aprendizaje por patrones** — Aprende de correcciones manuales
4. **Parser multi-banco** — Soporta múltiples formatos de extractos
5. **Ciclo contable de cheques en 3 fases** — Modelo original de tránsito contable

### Características diferenciales:

- Aritmética exacta en columnas financieras (`Numeric 12,2`)
- Auditoría automática de operaciones (antes/después)
- Soft-delete con papelera de reciclaje
- Multi-tenancy con aislamiento completo
- 2FA por email + PIN + biometría (WebAuthn)
- OCR para cheques y comprobantes (Gemini Flash)
- Asistente IA conversacional con function calling
- Web Push notifications
- PWA instalable en navegador

---

## CONCLUSIÓN

La obra presentable es la **totalidad del código fuente del sistema en sus tres componentes** (backend, frontend web, frontend móvil), junto con sus configuraciones, migraciones de BD, tests y scripts de inicialización.

El sistema está **completo, compilado, testado y en funcionamiento en producción** (versión v3.12).
