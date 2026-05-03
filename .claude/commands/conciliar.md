# Flujo de Conciliación Manual — Julieta Arrazate

Usá este flujo cuando necesites conciliar sin abrir la app,
o para guiar a un empleado paso a paso.

---

## PASO 1 — Preparar el extracto

**Si es el primer extracto del mes:**
1. Ir a Dashboard → Paso 1 → "Subir nuevo extracto"
2. Subir el archivo .xlsx del Banco Macro
3. Verificar que cargó correctamente (ver cantidad de movimientos)

**Si ya hay extracto y recibiste Últimos Movimientos (UM):**
1. Ir a Dashboard → Paso 1 → "Agregar UM"
2. Subir el archivo de UM del día
3. Verificar: debe decir "X movimientos nuevos sumados"
4. Si dice "0 nuevos — ya existían": el archivo es viejo, no sumar

---

## PASO 2 — Conciliar una planilla de cliente

Por cada planilla que llegue de un cliente:

1. Dashboard → Paso 2
2. Seleccionar el cliente en el dropdown
3. Verificar la fecha de acreditación (cambiar si es necesario)
4. Subir la planilla .xlsx del cliente
5. El sistema concilia automáticamente

**Interpretar los resultados:**
- ✅ **ok** — acreditado correctamente
- ❌ **no está** — el monto no existe en el extracto → verificar con el cliente
- ⚠️ **sin datos (N mov.)** — hay N movimientos con ese monto pero falta CUIT/CBU → pedirle al cliente
- ⚠️ **no coincide (N mov.)** — tiene datos pero no matcheó → revisar CUIT o nombre
- 🔄 **duplicado** — ya estaba acreditado → no hacer nada

---

## PASO 3 — Revisar los que fallaron

Para cada fila con problema:
1. Historial → Ver planilla del cliente
2. Tocar ✏️ en la fila problemática
3. Buscar manualmente en Movimientos el movimiento correcto
   - Filtrar por monto, titular o fecha
4. Una vez identificado, cambiar el estado a "ok"
5. El sistema aprende este patrón para la próxima vez

---

## PASO 4 — Exportar para el contador

Al final del día:
1. Ir a Movimientos
2. Verificar que todo esté bien
3. Tocar "📤 Para contador" → descarga Excel con formato Macro
4. Enviar al contador

---

## PASO 5 — Verificación final

Checklist antes de cerrar:
- [ ] Todos los clientes del día conciliados
- [ ] Sin "sin datos" pendientes sin revisar
- [ ] Extracto exportado para el contador
- [ ] ¿Llegaron UM de hoy? Si sí, agregar

---

## Comandos de API útiles (para Claude)

Si necesitás hacer algo por API directamente:

```bash
# Login
TOKEN=$(curl -s -X POST https://conciliacion-api.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@julieta.com","password":"admin123"}' | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

# Listar extractos
curl -s https://conciliacion-api.onrender.com/extractos \
  -H "Authorization: Bearer $TOKEN"

# Historial de planillas
curl -s "https://conciliacion-api.onrender.com/historial/planillas?limit=20" \
  -H "Authorization: Bearer $TOKEN"

# Ver insights de auditoría
curl -s "https://conciliacion-api.onrender.com/auditoria/insights?dias=30" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Casos especiales

**30+ movimientos del mismo monto:**
El sistema SIEMPRE pide identidad cuando un monto se repite.
Necesitás tener CUIT, CBU o número de cuenta en la planilla del cliente.
Sin eso → quedará en "sin datos" y tenés que revisar manualmente.

**Pago llegó lunes pero era del viernes:**
El sistema tiene 5 días de tolerancia automática.
No hace falta hacer nada especial — lo detecta solo.

**Cliente nuevo no está en el sistema:**
Al subir la planilla y poner el nombre del cliente,
el sistema lo crea automáticamente si no existe.

**Acceso para empleado:**
Crear usuario en Gestión de Usuarios con rol "Operador".
El operador puede subir extractos, agregar UM y conciliar.
No puede borrar ni ver la auditoría.
