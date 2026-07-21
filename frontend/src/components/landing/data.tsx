import { SecIcon } from './shared'

// Fortalezas reales auditadas (docs/AUDITORIA_EKP_2026-07.md §6) traducidas a
// lenguaje de contador — no de marketing. Cada card es verificable en el código.
export const CONFIANZA = [
  {
    icon: <SecIcon d="M12 6v12m-4-4.5c0 1.38 1.79 2.5 4 2.5s4-1.12 4-2.5-1.79-2.5-4-2.5-4-1.12-4-2.5S9.79 6 12 6s4 1.12 4 2.5" />,
    title: 'La plata se calcula en Decimal, no en float',
    desc: 'Todos los montos —del extracto a la planilla exportada— se manejan con precisión decimal exacta de punta a punta. No hay redondeos que se acumulen ni centavos que desaparecen entre pantallas.',
  },
  {
    icon: <SecIcon d={['M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2', 'M9 12l2 2 4-4']} />,
    title: 'Ningún asiento se edita a mano',
    desc: 'Los asientos contables son inmutables: una corrección nunca pisa un monto, se registra como reverso trazable — el original y la corrección quedan los dos en el libro, con quién y cuándo.',
  },
  {
    icon: <SecIcon d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />,
    title: 'Datos de tus clientes bajo Ley 25.326',
    desc: 'La información contable de cada cliente es sensible por definición. Cuadra cumple la ley argentina de protección de datos personales: no se usa ni se comparte para nada que no sea tu trabajo.',
  },
  {
    icon: <SecIcon d={['M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2']} />,
    title: 'Registro de auditoría completo',
    desc: 'Cada corrección, cada carga y cada cambio de estado queda registrado: quién lo hizo, cuándo y desde dónde. Es lo que te respalda si un cliente pregunta qué pasó con un movimiento.',
  },
  {
    icon: <SecIcon d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />,
    title: 'Cada estudio ve solo lo suyo',
    desc: 'Los datos están aislados por organización a nivel de base de datos. Un usuario de un cliente no puede ver, ni por error, información de otro.',
  },
  {
    icon: <SecIcon d={['M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 5.625c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125']} />,
    title: 'Backup diario, sin que hagas nada',
    desc: 'Copia completa de tus datos y los de tus clientes todas las noches, automática. No depende de que alguien se acuerde de hacerla.',
  },
]

export const COMO_FUNCIONA = [
  {
    n: '1',
    title: 'Importás el extracto',
    desc: 'Subís el Excel del banco tal como lo descargás — Macro, BBVA, Santander, Galicia, ICBC y otros 11 bancos argentinos más Mercado Pago. Cuadra detecta el formato solo.',
  },
  {
    n: '2',
    title: 'Matching automático',
    desc: 'El motor cruza cada movimiento contra la planilla del cliente por CUIT, CBU y número de referencia, con tolerancia de fecha. Lo que coincide se marca en el acto.',
  },
  {
    n: '3',
    title: 'Revisás las diferencias',
    desc: 'Solo lo ambiguo queda para vos. Confirmás o corregís, y el sistema aprende el patrón para la próxima vez. Export a Excel y PDF de cierre listos para el cliente.',
  },
]
