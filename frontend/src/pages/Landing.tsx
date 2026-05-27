import React, { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useThemeStore } from '@/store/theme'

// Hook para animar elementos al entrar en viewport
function useReveal() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { el.classList.add('revealed'); observer.disconnect() } },
      { threshold: 0.12 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return ref
}

const Reveal: React.FC<{ children: React.ReactNode; delay?: number; className?: string }> = ({ children, delay = 0, className = '' }) => {
  const ref = useReveal()
  return (
    <div
      ref={ref}
      className={`reveal-block ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  )
}

const features = [
  {
    icon: '⚡',
    title: 'Conciliación automática',
    desc: 'El motor cruza extractos bancarios con planillas de clientes por CUIT, CBU y referencia. Lo que cuadra, cuadra solo.',
  },
  {
    icon: '📸',
    title: 'Órdenes de pago con foto',
    desc: 'Registrá OPs firmadas desde el celular. Foto del comprobante, importe y cliente en tres pasos.',
  },
  {
    icon: '🏦',
    title: 'Cheques y pagos',
    desc: 'Seguimiento de cheques propios y de terceros. Alertas automáticas antes del vencimiento.',
  },
  {
    icon: '📊',
    title: 'Caja diaria',
    desc: 'Arqueo físico de billetes, saldo inicial, ingresos y pagos del día. El cruce en tiempo real.',
  },
  {
    icon: '🏢',
    title: 'Multi-empresa',
    desc: 'Gestionás todos tus clientes desde un solo lugar. Cada empresa ve solo sus propios datos.',
  },
  {
    icon: '📤',
    title: 'Export para el contador',
    desc: 'Excel formato Macro, PDF de cierre mensual y estado de cuenta por cliente. Todo listo para entregar.',
  },
]

const steps = [
  {
    n: '01',
    title: 'Subís el extracto',
    desc: 'Arrastrás el Excel del banco. El sistema lo parsea automáticamente.',
  },
  {
    n: '02',
    title: 'Cargás la planilla',
    desc: 'Subís la planilla de pagos de tu cliente. La conciliación corre sola.',
  },
  {
    n: '03',
    title: 'Revisás y exportás',
    desc: 'Lo que no cuadró queda para revisión manual. El resto ya está listo para el contador.',
  },
]

export const Landing: React.FC = () => {
  const { theme } = useThemeStore()

  return (
    <div className="min-h-screen bg-[#F4F4F5] dark:bg-[#0B0B0F] text-[#18181B] dark:text-[#E4E4E7] overflow-x-hidden">

      {/* ── Estilos de animación inline ── */}
      <style>{`
        .reveal-block {
          opacity: 0;
          transform: translateY(24px);
          transition: opacity 0.6s ease, transform 0.6s ease;
        }
        .reveal-block.revealed {
          opacity: 1;
          transform: translateY(0);
        }
        .hero-glow {
          animation: heroGlow 4s ease-in-out infinite alternate;
        }
        @keyframes heroGlow {
          0%   { opacity: 0.4; transform: scale(1); }
          100% { opacity: 0.7; transform: scale(1.08); }
        }
        .badge-pulse {
          animation: badgePulse 2s ease-in-out infinite;
        }
        @keyframes badgePulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.6; }
        }
        .float-card {
          animation: floatCard 3s ease-in-out infinite alternate;
        }
        @keyframes floatCard {
          0%   { transform: translateY(0px) rotate(-1deg); }
          100% { transform: translateY(-8px) rotate(0deg); }
        }
      `}</style>

      {/* ── Nav ── */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4
                      bg-[#F4F4F5]/80 dark:bg-[#0B0B0F]/80 backdrop-blur-md
                      border-b border-[#E4E4E7] dark:border-[#1E1E26]">
        <span className="text-lg font-bold tracking-tight dark:text-[#22C55E] text-[#5E6AD2]">
          Cuadra
        </span>
        <div className="flex items-center gap-3">
          <a href="#features" className="hidden sm:block text-sm text-[#71717A] hover:text-[#18181B] dark:hover:text-white transition-colors">
            Features
          </a>
          <a href="#como-funciona" className="hidden sm:block text-sm text-[#71717A] hover:text-[#18181B] dark:hover:text-white transition-colors">
            Cómo funciona
          </a>
          <Link
            to="/login"
            className="px-4 py-2 rounded-lg text-sm font-semibold
                       bg-[#5E6AD2] text-white hover:bg-[#4A55BE]
                       dark:bg-[#22C55E] dark:text-black dark:hover:bg-[#4ADE80]
                       transition-all duration-150 active:scale-[0.98]"
          >
            Ingresar →
          </Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative min-h-screen flex flex-col items-center justify-center px-6 pt-24 pb-16 text-center overflow-hidden">

        {/* Glow de fondo */}
        <div className="hero-glow absolute inset-0 pointer-events-none">
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full
                          bg-[#5E6AD2]/10 dark:bg-[#22C55E]/8 blur-3xl" />
        </div>

        {/* Badge */}
        <div className="badge-pulse inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium mb-6
                        bg-[#5E6AD2]/10 text-[#5E6AD2] border border-[#5E6AD2]/20
                        dark:bg-[#22C55E]/10 dark:text-[#22C55E] dark:border-[#22C55E]/20">
          <span className="w-1.5 h-1.5 rounded-full bg-current" />
          Sistema de conciliación bancaria
        </div>

        {/* Título */}
        <h1 className="text-5xl sm:text-6xl md:text-7xl font-bold tracking-tight leading-[1.1] mb-6 max-w-3xl">
          Los números{' '}
          <span className="text-[#5E6AD2] dark:text-[#22C55E]">cuadran</span>
          {' '}solos
        </h1>

        <p className="text-lg sm:text-xl text-[#71717A] dark:text-[#71717A] max-w-xl mb-10 leading-relaxed">
          Conciliá extractos bancarios, gestioná caja, cheques y órdenes de pago.
          Todo desde el celular o la web, para vos y tu equipo.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-3 mb-16">
          <Link
            to="/login"
            className="px-6 py-3 rounded-xl text-base font-semibold
                       bg-[#5E6AD2] text-white hover:bg-[#4A55BE]
                       dark:bg-[#22C55E] dark:text-black dark:hover:bg-[#4ADE80]
                       transition-all duration-150 active:scale-[0.98] shadow-lg"
          >
            Ingresar al sistema →
          </Link>
          <a
            href="#como-funciona"
            className="px-6 py-3 rounded-xl text-base font-medium
                       border border-[#E4E4E7] dark:border-[#1E1E26]
                       text-[#71717A] hover:text-[#18181B] dark:hover:text-white
                       hover:bg-white dark:hover:bg-[#16161C]
                       transition-all duration-150"
          >
            Ver cómo funciona
          </a>
        </div>

        {/* Mockup flotante */}
        <div className="float-card relative w-full max-w-sm mx-auto">
          <div className="rounded-2xl border border-[#E4E4E7] dark:border-[#1E1E26]
                          bg-white dark:bg-[#16161C] shadow-2xl overflow-hidden">
            {/* Barra superior mockup */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#E4E4E7] dark:border-[#1E1E26]">
              <span className="text-xs font-semibold text-[#5E6AD2] dark:text-[#22C55E]">Cuadra</span>
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-[#E4E4E7] dark:bg-[#1E1E26]" />
                <div className="w-2.5 h-2.5 rounded-full bg-[#E4E4E7] dark:bg-[#1E1E26]" />
                <div className="w-2.5 h-2.5 rounded-full bg-[#22C55E]" />
              </div>
            </div>
            {/* Filas mockup conciliación */}
            <div className="p-4 space-y-2">
              {[
                { label: 'Green SRL', monto: '$124.500', estado: 'ok' },
                { label: 'Tucu Inversiones', monto: '$89.200', estado: 'ok' },
                { label: 'David Prop.', monto: '$212.000', estado: 'warn' },
                { label: 'Innova SA', monto: '$56.800', estado: 'ok' },
              ].map((row, i) => (
                <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg
                                        bg-[#F4F4F5] dark:bg-[#111116]">
                  <div className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${row.estado === 'ok' ? 'bg-[#22C55E]' : 'bg-[#F59E0B]'}`} />
                    <span className="text-xs font-medium text-[#18181B] dark:text-[#E4E4E7]">{row.label}</span>
                  </div>
                  <span className="text-xs font-mono text-[#71717A]">{row.monto}</span>
                </div>
              ))}
              <div className="pt-2 flex items-center justify-between">
                <span className="text-xs text-[#71717A]">3 conciliados · 1 pendiente</span>
                <span className="text-xs font-semibold text-[#22C55E]">↓ Exportar</span>
              </div>
            </div>
          </div>

          {/* Card flotante de caja */}
          <div className="absolute -right-4 -bottom-4 rounded-xl border border-[#E4E4E7] dark:border-[#1E1E26]
                          bg-white dark:bg-[#16161C] shadow-xl p-3 w-40">
            <p className="text-2xs font-semibold text-[#71717A] uppercase tracking-wider mb-1">Caja hoy</p>
            <p className="text-base font-bold font-mono text-[#18181B] dark:text-[#E4E4E7]">$482.300</p>
            <p className="text-2xs text-[#22C55E] font-semibold mt-0.5">✓ Cuadra</p>
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className="px-6 py-24 max-w-5xl mx-auto">
        <Reveal className="text-center mb-16">
          <p className="text-sm font-semibold text-[#5E6AD2] dark:text-[#22C55E] uppercase tracking-wider mb-3">
            Todo en un lugar
          </p>
          <h2 className="text-3xl sm:text-4xl font-bold">
            Diseñado para el trabajo diario
          </h2>
        </Reveal>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((f, i) => (
            <Reveal key={f.title} delay={i * 80}>
              <div className="h-full rounded-2xl border border-[#E4E4E7] dark:border-[#1E1E26]
                              bg-white dark:bg-[#16161C]
                              hover:border-[#5E6AD2]/40 dark:hover:border-[#22C55E]/30
                              hover:shadow-lg transition-all duration-200 p-6">
                <div className="text-3xl mb-4">{f.icon}</div>
                <h3 className="font-semibold text-base mb-2">{f.title}</h3>
                <p className="text-sm text-[#71717A] leading-relaxed">{f.desc}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── Cómo funciona ── */}
      <section id="como-funciona" className="px-6 py-24 bg-white dark:bg-[#111116]">
        <div className="max-w-4xl mx-auto">
          <Reveal className="text-center mb-16">
            <p className="text-sm font-semibold text-[#5E6AD2] dark:text-[#22C55E] uppercase tracking-wider mb-3">
              Simple por diseño
            </p>
            <h2 className="text-3xl sm:text-4xl font-bold">
              De la planilla al Excel del contador
            </h2>
            <p className="text-[#71717A] mt-4 max-w-lg mx-auto">
              En tres pasos. Sin configuración compleja.
            </p>
          </Reveal>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {steps.map((s, i) => (
              <Reveal key={s.n} delay={i * 120}>
                <div className="relative">
                  {/* Línea conectora */}
                  {i < 2 && (
                    <div className="hidden md:block absolute top-6 left-full w-full h-px
                                    bg-gradient-to-r from-[#E4E4E7] dark:from-[#1E1E26] to-transparent
                                    -translate-x-4" />
                  )}
                  <div className="text-4xl font-bold font-mono
                                  text-[#5E6AD2]/20 dark:text-[#22C55E]/20 mb-4">
                    {s.n}
                  </div>
                  <h3 className="font-semibold text-lg mb-2">{s.title}</h3>
                  <p className="text-sm text-[#71717A] leading-relaxed">{s.desc}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Para tu equipo ── */}
      <section className="px-6 py-24 max-w-4xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          <Reveal>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Desde el celular o la web
            </h2>
            <p className="text-[#71717A] leading-relaxed mb-6">
              Instalala como app en el celular para registrar OPs y cheques en movimiento.
              Usá la web para subir extractos, conciliar y exportar al contador.
            </p>
            <ul className="space-y-3">
              {[
                'PWA instalable — sin App Store, sin Play Store',
                'Android e iPhone',
                'Funciona sin conexión para consultas',
                'Actualizaciones automáticas — sin reinstalar',
              ].map(item => (
                <li key={item} className="flex items-start gap-3 text-sm">
                  <span className="text-[#22C55E] font-bold mt-0.5">✓</span>
                  <span className="text-[#71717A]">{item}</span>
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={150}>
            <div className="rounded-2xl border border-[#E4E4E7] dark:border-[#1E1E26]
                            bg-white dark:bg-[#16161C] p-6 space-y-4">
              <div className="flex items-center gap-3 pb-4 border-b border-[#E4E4E7] dark:border-[#1E1E26]">
                <div className="w-10 h-10 rounded-xl bg-[#5E6AD2]/10 dark:bg-[#22C55E]/10
                                flex items-center justify-center text-xl">
                  📱
                </div>
                <div>
                  <p className="font-semibold text-sm">Campo / cobranza</p>
                  <p className="text-xs text-[#71717A]">Celular · PWA instalada</p>
                </div>
              </div>
              <div className="flex items-center gap-3 pb-4 border-b border-[#E4E4E7] dark:border-[#1E1E26]">
                <div className="w-10 h-10 rounded-xl bg-[#5E6AD2]/10 dark:bg-[#22C55E]/10
                                flex items-center justify-center text-xl">
                  💻
                </div>
                <div>
                  <p className="font-semibold text-sm">Contabilidad / conciliación</p>
                  <p className="text-xs text-[#71717A]">Web · cualquier navegador</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#5E6AD2]/10 dark:bg-[#22C55E]/10
                                flex items-center justify-center text-xl">
                  👁
                </div>
                <div>
                  <p className="font-semibold text-sm">Supervisión / auditoría</p>
                  <p className="text-xs text-[#71717A]">Web o celular · modo lectura</p>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── CTA final ── */}
      <section className="px-6 py-24 bg-white dark:bg-[#111116]">
        <Reveal className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            ¿Ya tenés acceso?
          </h2>
          <p className="text-[#71717A] mb-8">
            El sistema requiere cuenta habilitada. Si sos parte de un equipo que ya usa Cuadra, ingresá directamente.
          </p>
          <Link
            to="/login"
            className="inline-flex px-8 py-4 rounded-xl text-base font-semibold
                       bg-[#5E6AD2] text-white hover:bg-[#4A55BE]
                       dark:bg-[#22C55E] dark:text-black dark:hover:bg-[#4ADE80]
                       transition-all duration-150 active:scale-[0.98] shadow-lg shadow-[#5E6AD2]/20 dark:shadow-[#22C55E]/20"
          >
            Ingresar al sistema →
          </Link>
        </Reveal>
      </section>

      {/* ── Footer ── */}
      <footer className="px-6 py-8 border-t border-[#E4E4E7] dark:border-[#1E1E26]">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-sm font-semibold text-[#5E6AD2] dark:text-[#22C55E]">Cuadra</span>
          <div className="flex items-center gap-6 text-xs text-[#71717A]">
            <Link to="/privacidad" className="hover:text-[#18181B] dark:hover:text-white transition-colors">
              Política de privacidad
            </Link>
            <Link to="/terminos" className="hover:text-[#18181B] dark:hover:text-white transition-colors">
              Términos y condiciones
            </Link>
          </div>
          <span className="text-xs text-[#A1A1AA]">
            © {new Date().getFullYear()} Julieta Arrazate
          </span>
        </div>
      </footer>
    </div>
  )
}
