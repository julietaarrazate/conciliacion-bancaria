# Roadmap — Sistema de Conciliación Bancaria

> ⚠️ **DESACTUALIZADO** (auditoría 2026-07-10): varios ítems ya están hechos
> (multi-banco con detección automática, monitoreo, backups) — no planificar
> sesiones contra este archivo hasta reescribirlo. Estado real y prioridades
> vigentes: [`docs/AUDITORIA_EKP_2026-07.md`](docs/AUDITORIA_EKP_2026-07.md) §8.

Plan de evolución del producto pensando en clientes piloto y venta a
financieras, cooperativas y estudios contables.

---

## Fase 1 — Producto listo para piloto (4-6 semanas)

### Multi-banco (crítico)
Hoy el parser solo lee extractos Banco Macro. Sin más bancos no se
puede vender a clientes externos.

- [ ] Parser Banco Galicia (formato Excel propio)
- [ ] Parser Banco BBVA
- [ ] Parser Banco Santander
- [ ] Parser ICBC
- [ ] Detector automático de banco por estructura del archivo
- [ ] Tests con extractos reales de cada banco

### Onboarding self-service
Hoy un cliente nuevo no puede arrancar solo. Se necesita configuración
manual de organización, clientes, plan de cuentas.

- [ ] Wizard de bienvenida al primer login
- [ ] Carga de plan de cuentas base + customización
- [ ] Importación masiva de clientes desde Excel
- [ ] Tour guiado de las 5 pantallas principales
- [ ] Datos de demo opcionales para explorar la app

### Infraestructura paga
Render free tier se duerme y tarda 30s en despertar. Inaceptable para
clientes que pagan.

- [ ] Migrar a Render Starter (USD 7/mes) o equivalente
- [ ] SLA documentado (99% uptime, soporte 24h hábiles)
- [ ] Backup diario fuera de Neon (S3 o Drive)
- [ ] Monitor con alertas (Sentry o similar)
- [ ] Página de status pública

### Legal y comercial
- [ ] Términos de servicio
- [ ] Política de privacidad
- [ ] Contrato de prestación de servicios (revisado por abogado)
- [ ] Inscripción de la base de datos en AAIP (Ley 25.326)
- [ ] Pricing definido (recomendado: por organización, mensual)
- [ ] Manual de usuario en PDF

---

## Fase 2 — Funcionalidad core para financieras (6-8 semanas)

### Módulo Préstamos
Diferencia clave entre "herramienta contable" y "sistema de financiera".

- [ ] Modelo: Préstamo (capital, tasa, plazo, garante, fecha alta)
- [ ] Plan de pagos: cuotas con vencimiento, interés, capital
- [ ] Cálculo de intereses (sistema francés / alemán / americano)
- [ ] Gestión de cobros: cuota pagada, parcial, en mora
- [ ] Refinanciaciones / reestructuras
- [ ] Reportes: cartera vigente, en mora, recuperos
- [ ] Integración con motor contable (cada movimiento → asiento)

### Multi-moneda
- [ ] Tabla de tipos de cambio (diario, manual o API BCRA)
- [ ] Cuentas en USD / EUR además de ARS
- [ ] Conversión automática en asientos
- [ ] Reportes en moneda original + equivalente ARS
- [ ] Diferencias de cambio (resultado contable)

### Cuenta corriente formal por cliente
Hoy hay planillas y pagos pero no se cruzan en una vista clásica de
cta cte con saldo arrastrado.

- [ ] Vista débito / crédito / saldo por cliente
- [ ] Vinculación factura ↔ pago
- [ ] Saldo arrastrado mensual
- [ ] Aging de saldos por cliente (ya parcialmente hecho en /resumen)

---

## Fase 3 — Cumplimiento fiscal Argentina (4-6 semanas)

### Facturación electrónica AFIP / ARCA
Sin esto el ciclo legal queda abierto — siempre hay un paso "afuera".

- [ ] Integración con WSFE (Web Service Facturación Electrónica)
- [ ] Emisión de facturas A / B / C con CAE
- [ ] Notas de crédito / débito
- [ ] Libro IVA Ventas
- [ ] Libro IVA Compras
- [ ] Subdiarios

### Retenciones
- [ ] Retención Ganancias (RG 830)
- [ ] Retención IIBB (cada jurisdicción)
- [ ] Percepciones de IVA
- [ ] Certificados emitidos / recibidos
- [ ] Reportes SICORE / SIRCREB / SIRTAC

### Recibos PDF
- [ ] Generación automática al registrar pago
- [ ] Numeración secuencial controlada
- [ ] Envío por email al cliente

---

## Fase 4 — Hardening operacional (continuo)

### Seguridad pendiente
- [ ] Auto-logout por inactividad (client-side timer)
- [ ] 2FA opcional para superadmin
- [ ] Tabla de JWT revocados (logout invalida token de inmediato)
- [ ] Sanitización de logs (verificar que no muestren datos sensibles)
- [ ] Procedimiento de rotación de credenciales documentado

### Importación bancaria automática
- [ ] API Banco Macro empresa (cuando esté disponible)
- [ ] CBU/CVU webhook para acreditaciones instantáneas
- [ ] Conciliación incremental en lugar de subir Excel cada vez

### Notificaciones
- [ ] Email cuando una conciliación termina
- [ ] WhatsApp Business: aviso de acreditación al cliente final
- [ ] Recordatorio de cheques que vencen
- [ ] Resumen ejecutivo semanal por email

---

## Fase 5 — Mejoras de producto (oportunista)

### UI más moderna
- [ ] Dashboard con gráficos (Recharts o similar)
- [ ] Skeletons en lugar de spinners
- [ ] Toast notifications uniformes
- [ ] Animaciones de transición entre pantallas
- [ ] Empty states ilustrados
- [ ] Mejor jerarquía tipográfica
- [ ] Modo de alta densidad (más data por pantalla)

### Mobile
- [ ] App nativa React Native (elimina problemas de PWA en Android)
- [ ] Push notifications nativas
- [ ] Biometría para login

### Reportes
- [ ] Generación de PDF imprimible (balance, sumas y saldo, libro mayor)
- [ ] Reportes programados (mensual al email)
- [ ] Dashboard configurable por usuario (drag&drop de KPIs)

---

## Lo que decidimos NO hacer (al menos por ahora)

- Compete con Mambu / Bantotal / Temenos (cores bancarios) — escala
  fuera de alcance de un equipo chico
- Licencia BCRA / cumplimiento UIF pesado — requiere infraestructura
  legal y compliance dedicado
- Conexión a Central de Deudores BCRA — solo si hay cliente regulado
  que lo pida
- Cobranza judicial integrada — preferible derivar a estudios externos

---

## Mercado objetivo

**Tier 1 — donde competimos y ganamos**
- Estudios contables chicos y medianos (1-10 personas)
- Financieras locales no reguladas
- Mutuales chicas
- Cooperativas de crédito barriales
- Prestamistas formales

**Competencia directa**: Xubio, Colppy, Tango Gestión, Holded, Alegra.
**Diferencial**: motor de conciliación con scoring + IA de aprendizaje,
UX moderna, multi-tenant nativo, foco operacional (no solo contable).

---

## Pricing tentativo

| Plan | Precio (USD/mes) | Incluye |
|------|----------------|---------|
| Básico | 30-50 | 1 organización, 2 usuarios, 1 banco, 500 mov/mes |
| Pro | 80-120 | 1 organización, 10 usuarios, multi-banco, ilimitado |
| Multi | 200-350 | Multi-organización (estudios contables) |
| Enterprise | A medida | SLA dedicado, multi-tenant aislado |

Setup gratis primer mes piloto.
