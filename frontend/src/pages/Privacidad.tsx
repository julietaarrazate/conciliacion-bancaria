import React from 'react'
import { Link } from 'react-router-dom'

export const Privacidad: React.FC = () => {
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
            to="/terminos"
            className="text-sm text-gray-500 dark:text-zinc-400 hover:text-gray-700 dark:hover:text-zinc-200 transition-colors"
          >
            Términos y Condiciones
          </Link>
        </div>

        <div className="bg-white dark:bg-white/5 border border-gray-100 dark:border-white/10 rounded-2xl p-8 space-y-8">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white mb-1">
              Política de Privacidad
            </h1>
            <p className="text-sm text-gray-500 dark:text-zinc-400">
              Cuadra — Sistema de Conciliación Bancaria
            </p>
            <p className="text-xs text-gray-400 dark:text-zinc-500 mt-1">
              Última actualización: 26 de mayo de 2026
            </p>
          </div>

          <Section title="1. Responsable del tratamiento">
            <p>
              El responsable del tratamiento de los datos personales es <strong>Julieta Arrazate</strong>{' '}
              (julietaarrazate@gmail.com), con domicilio en la República Argentina.
            </p>
            <p>
              El sistema Cuadra es un software de gestión contable y conciliación bancaria de uso
              privado, destinado a empresas y profesionales de Argentina.
            </p>
          </Section>

          <Section title="2. Datos que recopilamos">
            <p>Recopilamos únicamente los datos necesarios para la prestación del servicio:</p>
            <ul>
              <li>
                <strong>Datos de acceso:</strong> nombre completo, dirección de correo electrónico,
                contraseña (almacenada con hash irreversible pbkdf2_sha256).
              </li>
              <li>
                <strong>Datos financieros:</strong> extractos bancarios, planillas de pago, CUITs,
                CBUs, importes, titulares de cuentas y referencias de movimientos aportados por el
                usuario para fines de conciliación.
              </li>
              <li>
                <strong>Datos de auditoría:</strong> registros de acceso, acciones realizadas en
                el sistema e identificador de IP, para fines de seguridad y trazabilidad.
              </li>
              <li>
                <strong>Notificaciones push (opcional):</strong> si el usuario habilita las
                notificaciones, se almacena el endpoint de suscripción del navegador.
              </li>
            </ul>
          </Section>

          <Section title="3. Finalidad del tratamiento">
            <p>Los datos son utilizados exclusivamente para:</p>
            <ul>
              <li>Proveer las funcionalidades del sistema de conciliación bancaria.</li>
              <li>Autenticar y autorizar el acceso de usuarios.</li>
              <li>Generar reportes, exportaciones y resúmenes financieros internos.</li>
              <li>Enviar alertas y notificaciones configuradas por el usuario.</li>
              <li>Mantener registros de auditoría para seguridad y cumplimiento interno.</li>
            </ul>
            <p>
              Los datos no son utilizados para publicidad, perfilado comercial ni compartidos con
              terceros salvo obligación legal expresa.
            </p>
          </Section>

          <Section title="4. Base legal">
            <p>
              El tratamiento se realiza en el marco de la{' '}
              <strong>Ley 25.326 de Protección de Datos Personales</strong> de la República
              Argentina y su Decreto Reglamentario 1558/2001. La base legal es el consentimiento
              del titular y la ejecución de la relación contractual de servicio.
            </p>
          </Section>

          <Section title="5. Destinatarios y transferencias">
            <p>
              Los datos se almacenan en servidores de <strong>Neon (PostgreSQL)</strong> con
              infraestructura en Estados Unidos bajo el programa de Privacy Shield / acuerdos de
              transferencia internacional vigentes. La base de datos se accede exclusivamente a
              través de conexión cifrada (TLS).
            </p>
            <p>
              El frontend se despliega en <strong>Vercel</strong> y el backend en{' '}
              <strong>Render</strong>. Ningún tercero recibe datos personales con fines propios.
            </p>
          </Section>

          <Section title="6. Plazo de conservación">
            <p>
              Los datos se conservan mientras la cuenta esté activa. Ante solicitud de baja, los
              datos se eliminan en un plazo máximo de 30 días hábiles, salvo obligación legal de
              conservación.
            </p>
            <p>
              Los registros de auditoría se conservan por 2 años por razones de seguridad.
            </p>
          </Section>

          <Section title="7. Derechos del titular">
            <p>
              En virtud de la Ley 25.326, el titular de los datos tiene derecho a:
            </p>
            <ul>
              <li>
                <strong>Acceso:</strong> solicitar qué datos personales suyos están almacenados.
              </li>
              <li>
                <strong>Rectificación:</strong> corregir datos inexactos o incompletos.
              </li>
              <li>
                <strong>Supresión:</strong> solicitar la eliminación de sus datos ("derecho al
                olvido"), salvo obligación legal de conservación.
              </li>
              <li>
                <strong>Confidencialidad:</strong> recibir tratamiento confidencial de sus datos.
              </li>
            </ul>
            <p>
              Las solicitudes deben enviarse a <strong>julietaarrazate@gmail.com</strong> con
              asunto "Solicitud Ley 25.326". Se responderá en un plazo máximo de 5 días hábiles.
            </p>
            <p className="text-sm text-gray-500 dark:text-zinc-400">
              La Dirección Nacional de Protección de Datos Personales (DNPDP / AAIP) es el
              organismo de control.
            </p>
          </Section>

          <Section title="8. Seguridad">
            <p>
              Se implementan las siguientes medidas técnicas y organizativas:
            </p>
            <ul>
              <li>Contraseñas almacenadas con hash irreversible (pbkdf2_sha256).</li>
              <li>Comunicaciones cifradas mediante TLS/HTTPS en todos los endpoints.</li>
              <li>Autenticación por token JWT con expiración de 8 horas.</li>
              <li>Rate limiting en endpoints de autenticación.</li>
              <li>Registros de auditoría de acceso y operaciones.</li>
              <li>Acceso restringido por roles (superadmin, admin, operador, revisor).</li>
              <li>Backups cifrados diarios enviados por email.</li>
            </ul>
          </Section>

          <Section title="9. Cookies y tecnologías similares">
            <p>
              El sistema no utiliza cookies de rastreo ni publicidad. Utiliza{' '}
              <code>localStorage</code> del navegador para almacenar el token de sesión JWT y
              preferencias de interfaz (tema, organización activa). Estos datos no se transmiten
              a terceros.
            </p>
          </Section>

          <Section title="10. Cambios a esta política">
            <p>
              Cualquier modificación a esta política será notificada al correo registrado con al
              menos 7 días de anticipación. El uso continuado del sistema implica la aceptación
              de los términos vigentes.
            </p>
          </Section>

          <Section title="11. Contacto">
            <p>
              Para consultas sobre esta política:{' '}
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
      <div className="text-sm text-gray-600 dark:text-zinc-400 space-y-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_strong]:text-gray-800 [&_strong]:dark:text-zinc-200 [&_code]:font-mono [&_code]:text-xs [&_code]:bg-gray-100 [&_code]:dark:bg-white/10 [&_code]:px-1 [&_code]:rounded">
        {children}
      </div>
    </section>
  )
}
