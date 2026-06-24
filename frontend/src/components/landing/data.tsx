import { SecIcon } from './shared'

export const STATS = [
  { label: 'para conciliar 100 movimientos', numericEnd: 2,  prefix: '< ', suffix: ' min' },
  { label: 'bancos argentinos soportados',   numericEnd: 10, prefix: '',   suffix: '+' },
  { label: 'instalaciones necesarias',       numericEnd: 0,  prefix: '',   suffix: '' },
  { label: 'para estar operativo',           numericEnd: 24, prefix: '',   suffix: 'hs' },
]

export const MOCKUP_ROWS = [
  { cliente: 'Cliente Norte SRL',  importe: '$124.500', ok: true  },
  { cliente: 'Constructora Sur',   importe: '$89.200',  ok: true  },
  { cliente: 'Distribuidora Este', importe: '$212.000', ok: false },
  { cliente: 'Servicios Centro',   importe: '$56.800',  ok: true  },
  { cliente: 'Comercial Oeste',    importe: '$98.400',  ok: true  },
]

export const SECURITY = [
  { icon: <SecIcon d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />, title: 'Acceso protegido siempre', desc: 'Las sesiones se cierran automáticamente por inactividad. Sin tu clave no puede entrar nadie más, aunque tengan el dispositivo.' },
  { icon: <SecIcon d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />, title: 'Datos separados por empresa', desc: 'Cada empresa ve solo sus propios datos. Imposible que un usuario de una empresa vea información de otra.' },
  { icon: <SecIcon d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />, title: 'Contraseñas cifradas', desc: 'Las contraseñas se guardan cifradas. Aunque alguien accediera a la base de datos, no podría leerlas.' },
  { icon: <SecIcon d={['M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 5.625c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125']} />, title: 'Backup diario automático', desc: 'Copia completa de todos los datos cada noche. Si algo falla, recuperamos todo sin perder información.' },
  { icon: <SecIcon d={['M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2', 'M9 12l2 2 4-4']} />, title: 'Registro de actividad completo', desc: 'Cada acción queda registrada: quién hizo qué, cuándo y desde dónde. Ideal para auditorías internas.' },
  { icon: <SecIcon d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />, title: 'Ley de protección de datos', desc: 'Cumplimos la Ley 25.326 argentina. Tus datos y los de tus clientes son tuyos — no se usan para nada más.' },
]

export const FAQ = [
  { q: '¿Cuánto cuesta usar Cuadra?', a: 'El precio se ajusta según la cantidad de empresas y usuarios. Coordiná un contacto por WhatsApp y te paso la propuesta con condiciones para tu caso.' },
  { q: '¿Qué bancos soporta el sistema?', a: 'Banco Macro, BBVA, Santander, Galicia, ICBC y un parser genérico para extractos en formato Excel. Si tu banco no está, lo agregamos en el onboarding.' },
  { q: '¿Mis datos están seguros?', a: 'Sí. Los datos de cada empresa están aislados, las contraseñas se guardan cifradas, hay backup automático cada noche y un registro completo de quién hizo qué y cuándo. Todo por HTTPS.' },
  { q: '¿Funciona sin conexión?', a: 'Las consultas básicas sí (lectura de cache). Para cargar planillas, registrar pagos o conciliar necesitás conexión.' },
  { q: '¿Se conecta con ARCA?', a: 'Por ahora no directamente. Exporta Excel en formato Banco Macro y PDF de cierre mensual, todo listo para entregar al contador.' },
  { q: '¿Cuántos usuarios puedo tener?', a: 'Sin límite. Cada empresa puede tener todos los empleados que necesite, con roles diferenciados (admin, operador, solo lectura).' },
  { q: '¿Puedo importar mis datos viejos?', a: 'Sí. Las planillas y extractos en Excel se importan directamente. Para datos en otros formatos, lo coordinamos en el onboarding inicial.' },
]

export const COMPARISON = [
  { feature: 'Conciliar 100 movimientos', excel: '4–6 horas', cuadra: '2 minutos' },
  { feature: 'Errores humanos', excel: 'Frecuentes', cuadra: 'Mínimos (auto-detección)' },
  { feature: 'Acceso desde el celular', excel: 'No', cuadra: 'Sí, desde cualquier teléfono' },
  { feature: 'Multi-empresa', excel: 'Un archivo por empresa', cuadra: 'Todo en un sistema' },
  { feature: 'Backup automático', excel: 'Manual o ninguno', cuadra: 'Diario encriptado' },
  { feature: 'Auditoría de cambios', excel: 'Ninguna', cuadra: 'Log completo' },
  { feature: 'Trabajo en equipo', excel: 'Conflictos al editar', cuadra: 'En tiempo real' },
]

export const TESTIMONIALES = [
  {
    quote: 'Llevamos 12 clientes con extractos de distintos bancos. Lo que antes nos llevaba dos días ahora sale en una mañana. El export para el contador es impecable.',
    nombre: 'Lic. Beatriz Pereyra',
    rol: 'Estudio Ferreyra & Pereyra · Córdoba',
    inicial: 'B',
  },
  {
    quote: 'El módulo de cheques cambió todo. Antes se nos pasaban vencimientos; ahora el sistema avisa con días de anticipación y los rechazos los registramos en el acto.',
    nombre: 'Gonzalo Marchetti',
    rol: 'Administración · distribuidora mayorista, Mendoza',
    inicial: 'G',
  },
  {
    quote: 'Subí el extracto del banco, subí las planillas de tres clientes y en diez minutos tenía la conciliación lista. No lo podía creer la primera vez.',
    nombre: 'Lic. Claudia Insúa',
    rol: 'Contadora independiente · Buenos Aires',
    inicial: 'C',
  },
]
