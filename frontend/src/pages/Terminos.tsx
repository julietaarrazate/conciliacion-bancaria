import React from 'react'
import { Link } from 'react-router-dom'

export const Terminos: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0B0B0F] py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8 flex items-center gap-4">
          <Link
            to="/login"
            className="text-sm text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-200 transition-colors"
          >
            ← Volver
          </Link>
          <span className="text-gray-300 dark:text-zinc-700">|</span>
          <Link
            to="/privacidad"
            className="text-sm text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-200 transition-colors"
          >
            Política de Privacidad
          </Link>
        </div>

        <div className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-2xl p-8 space-y-8">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white mb-1">
              Términos y Condiciones de Uso
            </h1>
            <p className="text-sm text-gray-500 dark:text-zinc-400">
              Cuadra — Sistema de Conciliación Bancaria
            </p>
            <p className="text-xs text-gray-400 dark:text-zinc-500 mt-1">
              Última actualización: 12 de junio de 2026
            </p>
          </div>

          <Section title="1. Objeto e identificación">
            <p>
              El presente documento regula el acceso y uso del sistema <strong>Cuadra</strong>{' '}
              (en adelante "Cuadra" o "el Sistema"), una plataforma web de conciliación bancaria
              y gestión contable desarrollada y operada por <strong>Julieta Arrazate</strong>{' '}
              (julietaarrazate@gmail.com), con domicilio en la República Argentina (en adelante
              "la Proveedora").
            </p>
            <p>
              Al acceder o utilizar el Sistema, el usuario (persona física o jurídica, en adelante
              "el Usuario") acepta quedar vinculado por estos Términos y Condiciones. Si no está
              de acuerdo con ellos, no debe utilizar el Sistema.
            </p>
          </Section>

          <Section title="2. Acceso al sistema">
            <ul>
              <li>
                El acceso es restringido: solo usuarios habilitados por la Proveedora pueden
                ingresar mediante credenciales personales e intransferibles.
              </li>
              <li>
                El Usuario es responsable de mantener la confidencialidad de su contraseña y
                de todas las actividades realizadas bajo su cuenta.
              </li>
              <li>
                Ante sospechas de acceso no autorizado, el Usuario debe notificar de inmediato
                a{' '}
                <a
                  href="mailto:julietaarrazate@gmail.com"
                  className="text-violet-600 dark:text-violet-400 hover:underline"
                >
                  julietaarrazate@gmail.com
                </a>.
              </li>
              <li>
                Cuadra se reserva el derecho de suspender o cancelar el acceso ante uso
                indebido, incumplimiento de estos Términos o por razones de seguridad.
              </li>
            </ul>
          </Section>

          <Section title="3. Uso permitido">
            <p>El Sistema está destinado exclusivamente a:</p>
            <ul>
              <li>La conciliación de extractos bancarios con planillas de pagos.</li>
              <li>La gestión interna de cheques, pagos, gastos, caja y liquidaciones.</li>
              <li>La generación de reportes contables y financieros para uso interno.</li>
            </ul>
            <p>Queda expresamente prohibido:</p>
            <ul>
              <li>Compartir credenciales de acceso con terceros no autorizados.</li>
              <li>Intentar acceder a datos de otras organizaciones o usuarios.</li>
              <li>Realizar ingeniería inversa, modificar o redistribuir el Sistema.</li>
              <li>Utilizar el Sistema para actividades contrarias a la ley argentina.</li>
              <li>
                Realizar ataques de denegación de servicio, inyección de código o cualquier
                actividad que comprometa la seguridad del Sistema.
              </li>
            </ul>
          </Section>

          <Section title="4. Datos y confidencialidad">
            <p>
              Los datos financieros ingresados al Sistema son propiedad del Usuario. Cuadra
              se compromete a:
            </p>
            <ul>
              <li>No acceder a los datos del Usuario salvo para soporte técnico autorizado.</li>
              <li>
                Mantener confidencialidad sobre la información financiera procesada por el Sistema.
              </li>
              <li>
                Aplicar las medidas técnicas de seguridad descritas en la{' '}
                <Link to="/privacidad" className="text-violet-600 dark:text-violet-400 hover:underline">
                  Política de Privacidad
                </Link>.
              </li>
            </ul>
          </Section>

          <Section title="5. Datos de terceros cargados por el usuario">
            <p>
              Si el Usuario carga en el Sistema datos personales de clientes, proveedores,
              empleados u otros terceros, declara y garantiza que:
            </p>
            <ul>
              <li>
                Cuenta con base legal suficiente para incorporar esos datos a la plataforma
                conforme a la Ley 25.326 de Protección de Datos Personales.
              </li>
              <li>
                Ha cumplido con los deberes de información y, cuando corresponda, de
                consentimiento exigidos por la normativa aplicable respecto de dichos terceros.
              </li>
            </ul>
            <p>
              El Usuario es el único responsable por la licitud, calidad y pertinencia de los
              datos de terceros que incorpore al Sistema. Cuadra no adquiere la propiedad de
              esos datos ni los trata con fines propios.
            </p>
          </Section>

          <Section title="6. Datos sensibles">
            <p>
              El Usuario se compromete a no cargar en el Sistema datos sensibles en los términos
              del Art. 2° de la Ley 25.326 (datos referidos a origen racial o étnico, opiniones
              políticas, convicciones religiosas o morales, afiliación sindical, información
              referente a la salud o a la vida sexual), salvo que sea estrictamente necesario,
              lícito y bajo su exclusiva responsabilidad, con la base legal correspondiente.
            </p>
          </Section>

          <Section title="7. Disponibilidad del servicio">
            <p>
              Cuadra procurará mantener el Sistema disponible de manera continua, pero no
              garantiza disponibilidad ininterrumpida. El Sistema puede experimentar
              interrupciones por mantenimiento, actualizaciones o causas ajenas a la Proveedora
              (fallas de terceros proveedores de infraestructura como Render, Vercel o Neon).
            </p>
            <p>
              Se implementa monitoreo continuo para minimizar el tiempo de inactividad no
              planificado.
            </p>
          </Section>

          <Section title="8. Propiedad intelectual">
            <p>
              El Sistema, su código fuente, diseño, logotipos y documentación son propiedad
              exclusiva de Julieta Arrazate, con obra registrada ante la Dirección Nacional
              del Derecho de Autor (DNDA). El acceso al Sistema no otorga al Usuario ningún
              derecho de propiedad intelectual sobre los mismos.
            </p>
            <p>
              Queda prohibido copiar, reproducir, modificar, distribuir, sublicenciar,
              descompilar, realizar ingeniería inversa o explotar total o parcialmente el
              Sistema sin autorización previa y expresa, salvo en la medida permitida por la ley.
            </p>
          </Section>

          <Section title="9. Limitación de responsabilidad">
            <p>Cuadra no será responsable por:</p>
            <ul>
              <li>
                Decisiones financieras o contables tomadas en base a los resultados del Sistema.
              </li>
              <li>Pérdidas derivadas de errores en los datos ingresados por el Usuario.</li>
              <li>
                Interrupciones del servicio ocasionadas por terceros proveedores de
                infraestructura.
              </li>
              <li>
                Daños indirectos, lucro cesante, pérdida de chance o pérdida de datos por
                causas de fuerza mayor o ajenas al control razonable de la Proveedora.
              </li>
              <li>
                Fallas, rechazos, bloqueos o decisiones adoptadas por servicios de terceros
                integrados a la plataforma (Gemini, Resend u otros).
              </li>
            </ul>
            <p>
              El Sistema es una herramienta de apoyo. La validación final de conciliaciones
              y registros contables es responsabilidad del contador y del Usuario.
            </p>
          </Section>

          <Section title="10. Indemnidad">
            <p>
              El Usuario se obliga a mantener indemne a Cuadra y a la Proveedora frente a
              cualquier reclamo, demanda, daño o gasto (incluyendo honorarios legales)
              originado en actos, omisiones, contenidos o incumplimientos imputables al
              propio Usuario, incluyendo el tratamiento indebido de datos de terceros que
              hubiera cargado en el Sistema.
            </p>
            <p>
              Esta obligación no aplica respecto de reclamos originados exclusivamente en
              hechos imputables a Cuadra.
            </p>
          </Section>

          <Section title="11. Respaldo de datos">
            <p>
              Cuadra realiza backups diarios automáticos conservados por 30 días. Sin embargo,
              se recomienda al Usuario exportar regularmente sus datos mediante las funciones
              de exportación disponibles en el Sistema (Excel, PDF).
            </p>
          </Section>

          <Section title="12. Modificaciones">
            <p>
              Cuadra puede modificar estos Términos en cualquier momento para reflejar cambios
              legales, técnicos u operativos. Los cambios serán notificados al correo
              electrónico registrado con al menos 7 días de anticipación. El uso continuado
              del Sistema después de esa fecha implica la aceptación de los nuevos Términos.
            </p>
          </Section>

          <Section title="13. Ley aplicable y jurisdicción">
            <p>
              Estos Términos se rigen por las leyes de la República Argentina. Para cualquier
              controversia, las partes se someten a la jurisdicción de los tribunales ordinarios
              de la Ciudad Autónoma de Buenos Aires, renunciando a cualquier otro fuero o
              jurisdicción que pudiera corresponder.
            </p>
          </Section>

          <Section title="14. Contacto">
            <p>
              Para consultas, reclamos o notificaciones:{' '}
              <a
                href="mailto:julietaarrazate@gmail.com"
                className="text-violet-600 dark:text-violet-400 hover:underline"
              >
                julietaarrazate@gmail.com
              </a>
            </p>
          </Section>
        </div>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold text-gray-800 dark:text-zinc-200">{title}</h2>
      <div className="text-sm text-gray-600 dark:text-zinc-400 space-y-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_strong]:text-gray-800 [&_strong]:dark:text-zinc-200">
        {children}
      </div>
    </section>
  )
}
