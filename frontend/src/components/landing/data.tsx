/**
 * Copy de la landing. Reglas (pedido de la operadora, oct 2026):
 *  - un titular y una bajada por sección; la bajada suma información, no repite;
 *  - voz de contador/dueño de pyme argentina, sin jerga interna del sistema;
 *  - solo cosas que el producto hace hoy (ver CLAUDE.md y /docs). Sin números
 *    de ahorro inventados ni testimonios ficticios.
 */

export const BANCOS = [
  'Macro', 'BBVA', 'Santander', 'Galicia', 'ICBC', 'Nación', 'Provincia', 'Ciudad', 'HSBC',
  'Mercado Pago', 'Credicoop', 'Supervielle', 'Patagonia', 'Bancor', 'Rioja', 'La Pampa',
]

export const HERO_FACTS = ['Extractos en Excel o PDF', `${BANCOS.length} bancos argentinos`, 'En la web y en el celular']

export const PASOS = [
  {
    titulo: 'Subí el extracto',
    texto: 'En Excel o PDF, de Macro, Galicia, Santander, Nación y doce bancos más. Los últimos movimientos del día se suman sin duplicar.',
  },
  {
    titulo: 'Sumá las planillas de tus clientes',
    texto: 'Cada cliente te la manda como quiere. La primera vez confirmás qué columna es qué y Cuadra lo recuerda para la próxima.',
  },
  {
    titulo: 'Revisá solo lo dudoso',
    texto: 'Lo que coincide por CUIT, CBU o titular queda acreditado. Si dos pagos tienen el mismo monto, te pregunta antes de decidir.',
  },
]

export const FUNCIONES = {
  control: {
    titulo: 'Control del banco',
    texto: 'Compara el saldo del banco en tus libros con el del extracto. Si no coincide, te dice cuánto falta y entre qué fechas.',
  },
  alertas: {
    titulo: 'Avisos antes de que sea tarde',
    texto: 'En el celular: cheques por vencer, cobros sin identificar hace más de una semana y vencimientos impositivos.',
  },
  cheques: {
    titulo: 'Cheques con una foto',
    texto: 'Sacás la foto y se completan número, banco, librador, monto y fecha. Varios cheques en la misma foto.',
  },
  facturas: {
    titulo: 'Facturas de compra leídas solas',
    texto: 'Subís la factura, la revisás y queda cargada para el IVA y para los pagos.',
  },
  impuestos: {
    titulo: 'Impuestos y cierre del mes',
    texto: 'IVA con tus comprobantes de ARCA, Ingresos Brutos, Monotributo y sueldos. Y el Excel y el PDF de cierre para el contador.',
  },
}

export const CASOS = [
  {
    tag: 'Estudios contables',
    texto: 'Llevás varias empresas, cada una con su banco y sus clientes. Pasás de una a otra sin mezclar nada y cada una tiene su cierre.',
  },
  {
    tag: 'Empresas que cobran por transferencia',
    texto: 'Sabés qué cliente pagó, cuánto y cuándo, y qué plata entró sin identificar. Todos los días, no a fin de mes.',
  },
  {
    tag: 'Administraciones con cheques',
    texto: 'Cartera, depósitos y rechazos en un solo lugar, con aviso antes de cada vencimiento.',
  },
]

export const CONFIANZA = [
  { titulo: 'Cada empresa ve lo suyo', texto: 'Los datos de una empresa nunca se cruzan con los de otra.' },
  { titulo: 'Copia de seguridad diaria', texto: 'Todas las noches, de todos los datos.' },
  { titulo: 'Registro de cada cambio', texto: 'Quién hizo qué y cuándo, para cualquier revisión.' },
  { titulo: 'Permisos por persona', texto: 'Cada usuario ve y hace solo lo que le corresponde.' },
]

export const PRECIO_INCLUYE = [
  'Usuarios sin límite',
  'Varias empresas',
  'Puesta en marcha',
  'Capacitación al equipo',
  'Soporte directo por WhatsApp',
  'Actualizaciones incluidas',
]

export const FAQ = [
  {
    q: '¿Qué bancos acepta?',
    a: `${BANCOS.slice(0, -1).join(', ')} y ${BANCOS[BANCOS.length - 1]}, en Excel. También extractos en PDF. Si tu banco no está en la lista, lo sumamos.`,
  },
  {
    q: '¿Mis clientes tienen que cambiar sus planillas?',
    a: 'No. Cada uno te la manda en su formato. La primera vez confirmás qué columna es el monto, el CUIT o la fecha, y Cuadra lo recuerda para ese cliente.',
  },
  {
    q: '¿Qué pasa con los pagos que no puede identificar?',
    a: 'Quedan marcados para que los revises. Cuando hay dos pagos con el mismo monto, nunca decide solo: necesita un dato más, como el CUIT, el CBU o el titular. Y aprende de las correcciones que hacés.',
  },
  {
    q: '¿Se conecta con ARCA?',
    a: 'Importás el Excel de "Mis Comprobantes" y Cuadra lo compara con lo que ya cargaste antes de liquidar el IVA. Por ahora no emite facturas electrónicas.',
  },
  {
    q: '¿Mis datos están seguros?',
    a: 'Cada empresa ve solo sus datos, las contraseñas se guardan cifradas, se hace una copia de seguridad todas las noches y queda registro de cada cambio.',
  },
  {
    q: '¿Cómo empiezo?',
    a: 'Pedís la demo, te mostramos el sistema en vivo y armamos tu empresa con tus bancos y tus clientes. La capacitación está incluida.',
  },
]

export const VOLUMENES = ['Menos de 20 clientes', 'Entre 20 y 100 clientes', 'Más de 100 clientes']
