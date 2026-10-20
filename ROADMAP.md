# Roadmap — Sistema de Conciliación Bancaria

> Estado verificado contra el código en **oct 2026** (v3.31): `[x]` hecho, `[ ]` pendiente;
> los ítems a medio camino dicen *(parcial: …)*. Detalle de cada versión en
> [`CHANGELOG.md`](CHANGELOG.md); deuda técnica en [`ENGINEERING_AUDIT.md`](ENGINEERING_AUDIT.md).
> Lo concreto y más reciente está en "Pendiente para próximas sesiones" de `CLAUDE.md`.

Plan de evolución del producto pensando en clientes piloto y venta a
financieras, cooperativas y estudios contables.

---

## Fase 1 — Producto listo para piloto (4-6 semanas)

### Multi-banco (crítico)
Hecho: 16 bancos detectados en `excel_parser.py` (v3.15) + extractos en PDF (v3.31).

- [x] Parser Banco Galicia (parser genérico por encabezados, v3.15)
- [x] Parser Banco BBVA
- [x] Parser Banco Santander
- [x] Parser ICBC
- [ ] Detector automático de banco por estructura del archivo *(parcial: detecta por nombre del banco en el encabezado; por estructura solo Mercado Pago; PDF por membrete)*
- [ ] Tests con extractos reales de cada banco *(parcial: fixtures sintéticos; PDF reales se suman a `test_extracto_pdf_casos_dificiles.py`)*

### Onboarding self-service
Un cliente nuevo todavía no puede arrancar solo del todo.

- [ ] Wizard de bienvenida al primer login *(parcial: `OnboardingChecklist` de 3 pasos en el Dashboard, v3.10.3)*
- [ ] Carga de plan de cuentas base + customización *(parcial: el plan base se siembra al crear la org; no se puede editar)*
- [ ] Importación masiva de clientes desde Excel
- [ ] Tour guiado de las 5 pantallas principales
- [ ] Datos de demo opcionales para explorar la app

### Infraestructura paga
Render free tier se duerme y tarda 30s en despertar (hoy mitigado con
UptimeRobot + `db_keepalive`). Inaceptable para clientes que pagan.

- [ ] Migrar a Render Starter (USD 7/mes) o equivalente
- [ ] SLA documentado (99% uptime, soporte 24h hábiles)
- [x] Backup diario fuera de Neon (JSON gzip por email vía Resend, 03:00 ART)
- [x] Monitor con alertas (Sentry cableado back + front, v3.11.4 — falta confirmar DSN en producción)
- [ ] Página de status pública

### Legal y comercial
- [x] Términos de servicio (`/terminos`)
- [x] Política de privacidad (`/privacidad`)
- [ ] Contrato de prestación de servicios (revisado por abogado)
- [ ] Inscripción de la base de datos en AAIP (Ley 25.326)
- [ ] Pricing definido (recomendado: por organización, mensual) *(parcial: la landing muestra "Consultar precio", sin montos)*
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
Ya existe la vista de cta cte (`ctb_ctas_corrientes.py`, v3.6); falta el cruce factura ↔ pago.

- [x] Vista débito / crédito / saldo por cliente (v3.6)
- [ ] Vinculación factura ↔ pago
- [ ] Saldo arrastrado mensual *(parcial: saldo corrido en el detalle, pero con filtro de fecha arranca en 0)*
- [x] Aging de saldos por cliente (`/analisis/clientes-aging`)

---

## Fase 3 — Cumplimiento fiscal Argentina (4-6 semanas)

### Facturación electrónica AFIP / ARCA
Sin esto el ciclo legal queda abierto — siempre hay un paso "afuera".

- [x] Integración con WSFE (v3.24 — construida, desactivada a propósito en producción)
- [x] Emisión de facturas A / B / C con CAE
- [ ] Notas de crédito / débito
- [ ] Libro IVA Ventas *(parcial: import de "Mis Comprobantes" emitidos, v3.26; sin export Libro IVA Digital)*
- [ ] Libro IVA Compras *(parcial: "Mis Comprobantes" recibidos, v3.26, + facturas por mail, v3.30)*
- [ ] Subdiarios

### Retenciones
- [ ] Retención Ganancias (RG 830)
- [ ] Retención IIBB (cada jurisdicción)
- [ ] Percepciones de IVA *(parcial: carga manual en la liquidación de IVA, v3.26)*
- [ ] Certificados emitidos / recibidos
- [ ] Reportes SICORE / SIRCREB / SIRTAC

### Recibos PDF
- [ ] Generación automática al registrar pago
- [ ] Numeración secuencial controlada
- [ ] Envío por email al cliente

---

## Fase 4 — Hardening operacional (continuo)

### Seguridad pendiente
- [ ] Auto-logout por inactividad (client-side timer) *(parcial: bloqueo con PIN a los 5 min si el usuario lo activó; no cierra sesión)*
- [x] 2FA para superadmin/admin (código por email, v3.11; requiere `RESEND_API_KEY`)
- [x] Tabla de JWT revocados (logout invalida token de inmediato)
- [ ] Sanitización de logs (verificar que no muestren datos sensibles) *(parcial: Sentry sin PII; sin redactor en `logging_config.py`)*
- [ ] Procedimiento de rotación de credenciales documentado

### Importación bancaria automática
- [ ] API Banco Macro empresa (cuando esté disponible)
- [ ] CBU/CVU webhook para acreditaciones instantáneas
- [ ] Conciliación incremental en lugar de subir Excel cada vez *(parcial: merge de UM y "agregar solo los nuevos", pero sigue requiriendo subir archivo)*

### Notificaciones
- [ ] Email cuando una conciliación termina
- [ ] WhatsApp Business: aviso de acreditación al cliente final *(parcial: compartir manual por wa.me, v3.11.1)*
- [x] Recordatorio de cheques que vencen (web push diario 10:00 ART)
- [ ] Resumen ejecutivo semanal por email

---

## Fase 5 — Mejoras de producto (oportunista)

### UI más moderna
- [x] Dashboard con gráficos (`components/charts/`, propios)
- [ ] Skeletons en lugar de spinners *(parcial: `Skeleton.tsx` en varias páginas; quedan spinners)*
- [x] Toast notifications uniformes (`Toaster.tsx`)
- [x] Animaciones de transición entre pantallas (`.page-enter`)
- [ ] Empty states ilustrados
- [ ] Mejor jerarquía tipográfica *(parcial: Fraunces en la landing; app sin cambio global)*
- [ ] Modo de alta densidad (más data por pantalla)

### Mobile
- [ ] App nativa React Native (elimina problemas de PWA en Android)
- [ ] Push notifications nativas *(parcial: Web Push vía PWA)*
- [ ] Biometría para login *(parcial: WebAuthn desbloquea el PIN de la app, no el login)*

### Reportes
- [ ] Generación de PDF imprimible (balance, sumas y saldo, libro mayor) *(los reportes existen como vista/JSON, sin PDF)*
- [ ] Reportes programados (mensual al email)
- [ ] Dashboard configurable por usuario (drag&drop de KPIs)

---

## Lo que decidimos NO hacer (al menos por ahora)

- Competir con cores bancarios — escala fuera de alcance de un equipo chico
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

**Diferencial**: motor de conciliación con scoring + IA de aprendizaje,
UX moderna, multi-tenant nativo, foco operacional (no solo contable).
