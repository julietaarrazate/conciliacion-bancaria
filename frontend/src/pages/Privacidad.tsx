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
              Última actualización: 12 de junio de 2026
            </p>
          </div>

          <Section title="1. Responsable del tratamiento">
            <p>
              <strong>Cuadra</strong> es un sistema de gestión contable y conciliación bancaria
              desarrollado y operado por <strong>Julieta Arrazate</strong>{' '}
              (julietaarrazate@gmail.com), con domicilio en la República Argentina, responsable
              del tratamiento de los datos personales conforme a la{' '}
              <strong>Ley 25.326 de Protección de Datos Personales</strong> y su Decreto
              Reglamentario 1558/2001.
            </p>
            <p>
              El sistema está destinado a empresas y profesionales de Argentina que requieran
              herramientas de conciliación bancaria, gestión de cheques, caja, liquidaciones
              y contabilidad operativa.
            </p>
          </Section>

          <Section title="2. Datos que recopilamos">
            <p>Cuadra recopila únicamente los datos necesarios para la prestación del servicio:</p>
            <ul>
              <li>
                <strong>Datos de acceso:</strong> nombre completo, dirección de correo electrónico
                y contraseña (almacenada con hash irreversible pbkdf2_sha256).
              </li>
              <li>
                <strong>Datos financieros:</strong> extractos bancarios, planillas de pago, CUIT,
                CBU/CVU, importes, titulares de cuentas y referencias de movimientos aportados
                por el usuario para fines de conciliación.
              </li>
              <li>
                <strong>Datos de auditoría:</strong> registros de acceso, acciones realizadas en
                el sistema e identificador de IP, con fines de seguridad y trazabilidad interna.
              </li>
              <li>
                <strong>Notificaciones push (opcional):</strong> si el usuario habilita las
                notificaciones, se almacena el endpoint de suscripción del navegador.
              </li>
              <li>
                <strong>Imágenes de comprobantes (opcional):</strong> fotos de cheques y
                comprobantes de transferencia que el usuario adjunte al sistema, utilizadas
                para el reconocimiento óptico de caracteres (OCR).
              </li>
            </ul>
          </Section>

          <Section title="3. Finalidad del tratamiento">
            <p>Los datos son utilizados exclusivamente para:</p>
            <ul>
              <li>Proveer las funcionalidades del sistema (conciliación, cheques, caja, contabilidad).</li>
              <li>Autenticar y autorizar el acceso de usuarios por rol y organización.</li>
              <li>Generar reportes, exportaciones y resúmenes financieros internos.</li>
              <li>Enviar alertas, notificaciones push y correos operativos configurados por el usuario.</li>
              <li>Mantener registros de auditoría para seguridad y cumplimiento interno.</li>
              <li>Brindar soporte técnico cuando el usuario lo solicite.</li>
            </ul>
            <p>
              Los datos no son utilizados para publicidad, perfilado comercial ni compartidos con
              terceros salvo en los casos descritos en la sección 6.
            </p>
          </Section>

          <Section title="4. Base legal del tratamiento">
            <p>El tratamiento de datos personales se funda en:</p>
            <ul>
              <li>
                <strong>Ejecución del contrato:</strong> los datos son necesarios para que el
                sistema funcione.
              </li>
              <li>
                <strong>Consentimiento:</strong> al registrarse, el usuario acepta esta política.
                Puede revocarlo solicitando la baja de su cuenta.
              </li>
              <li>
                <strong>Interés legítimo:</strong> seguridad del sistema, prevención de fraude
                y mejora del servicio mediante datos agregados anónimos.
              </li>
            </ul>
          </Section>

          <Section title="5. Uso de inteligencia artificial">
            <p>
              Cuadra incorpora un asistente de inteligencia artificial y funciones de
              reconocimiento óptico de caracteres (OCR) sobre cheques y comprobantes de
              transferencia. Para ello utiliza la API de <strong>Gemini (Google)</strong>.
            </p>
            <p>
              Los datos que se envían a Gemini se limitan a lo estrictamente necesario para
              la funcionalidad solicitada: descripciones y montos de movimientos (asistente IA)
              e imágenes de cheques o comprobantes (OCR). Google procesa estos datos
              exclusivamente para generar la respuesta requerida.
            </p>
            <p>
              <strong>Cuadra no entrena modelos de inteligencia artificial propios ni
              generales con los datos de sus usuarios.</strong> Las correcciones manuales
              de conciliaciones mejoran la clasificación únicamente dentro de la cuenta
              del propio usuario (función de aprendizaje interno del sistema).
            </p>
          </Section>

          <Section title="6. Subprocesadores y transferencias internacionales">
            <p>
              Para prestar el servicio, Cuadra utiliza los siguientes proveedores. Cada uno
              trata datos exclusivamente para los fines indicados:
            </p>
            <div className="overflow-x-auto mt-2">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-white/10">
                    <th className="text-left py-2 pr-4 font-semibold text-gray-700 dark:text-zinc-300">Proveedor</th>
                    <th className="text-left py-2 pr-4 font-semibold text-gray-700 dark:text-zinc-300">Función</th>
                    <th className="text-left py-2 pr-4 font-semibold text-gray-700 dark:text-zinc-300">Datos involucrados</th>
                    <th className="text-left py-2 font-semibold text-gray-700 dark:text-zinc-300">País</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-white/5">
                  <tr>
                    <td className="py-2 pr-4">Neon (PostgreSQL)</td>
                    <td className="py-2 pr-4">Base de datos</td>
                    <td className="py-2 pr-4">Todos los datos del servicio</td>
                    <td className="py-2">EE. UU.</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">Render</td>
                    <td className="py-2 pr-4">Servidor backend (API)</td>
                    <td className="py-2 pr-4">Procesamiento de datos, logs de acceso</td>
                    <td className="py-2">EE. UU.</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">Vercel</td>
                    <td className="py-2 pr-4">Frontend (CDN)</td>
                    <td className="py-2 pr-4">Archivos estáticos, sin datos personales</td>
                    <td className="py-2">EE. UU.</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">Gemini (Google)</td>
                    <td className="py-2 pr-4">Asistente IA y OCR</td>
                    <td className="py-2 pr-4">Descripciones de movimientos, montos, imágenes de comprobantes</td>
                    <td className="py-2">EE. UU.</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-4">Resend</td>
                    <td className="py-2 pr-4">Correo electrónico transaccional</td>
                    <td className="py-2 pr-4">Email del destinatario, contenido del correo</td>
                    <td className="py-2">EE. UU.</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p>
              Las transferencias internacionales se realizan al amparo del{' '}
              <strong>Art. 12 de la Ley 25.326</strong>. Ningún subprocesador recibe datos
              con fines propios ni los comercializa de forma independiente.
            </p>
          </Section>

          <Section title="7. Plazo de conservación">
            <ul>
              <li>
                <strong>Datos de la cuenta:</strong> mientras la cuenta esté activa y hasta
                12 meses después de la baja, por razones contables y legales.
              </li>
              <li>
                <strong>Datos financieros:</strong> mientras el usuario los conserve en el
                sistema o hasta que solicite su eliminación.
              </li>
              <li>
                <strong>Backups:</strong> los respaldos completos se conservan por 30 días.
                Una solicitud de eliminación se replica en los backups en ese período.
              </li>
              <li>
                <strong>Registros de auditoría:</strong> 2 años por razones de seguridad
                y trazabilidad interna.
              </li>
              <li>
                <strong>Logs de servidor:</strong> 90 días, con fines de diagnóstico y seguridad.
              </li>
            </ul>
          </Section>

          <Section title="8. Datos de terceros cargados por el usuario">
            <p>
              Si el usuario carga en Cuadra datos personales de clientes, proveedores,
              empleados u otros terceros, declara y garantiza que:
            </p>
            <ul>
              <li>
                Cuenta con base legal suficiente para incorporar esos datos a la plataforma.
              </li>
              <li>
                Ha cumplido con los deberes de información y, cuando corresponda, de
                consentimiento exigidos por la Ley 25.326 respecto de dichos terceros.
              </li>
            </ul>
            <p>
              El usuario es responsable por la licitud, calidad y pertinencia de los datos
              de terceros que incorpore al sistema. Cuadra no adquiere la propiedad de esos
              datos ni los trata con fines propios.
            </p>
          </Section>

          <Section title="9. Datos sensibles">
            <p>
              El usuario se compromete a no cargar en Cuadra datos sensibles en los términos
              del Art. 2° de la Ley 25.326 (datos referidos a origen racial o étnico, opiniones
              políticas, convicciones religiosas o morales, afiliación sindical, información
              referente a la salud o a la vida sexual), salvo que sea estrictamente necesario,
              lícito y bajo su exclusiva responsabilidad, con la base legal correspondiente.
            </p>
          </Section>

          <Section title="10. Derechos del titular">
            <p>
              En virtud de la Ley 25.326, el titular de los datos tiene derecho a:
            </p>
            <ul>
              <li>
                <strong>Acceso:</strong> conocer qué datos personales suyos están almacenados.
              </li>
              <li>
                <strong>Rectificación:</strong> corregir datos inexactos o incompletos.
              </li>
              <li>
                <strong>Supresión:</strong> solicitar la eliminación de sus datos ("derecho al
                olvido"), salvo obligación legal de conservación.
              </li>
              <li>
                <strong>Oposición:</strong> oponerse al tratamiento de sus datos por motivos
                legítimos.
              </li>
              <li>
                <strong>Portabilidad:</strong> exportar sus datos en un formato estándar
                (disponible mediante las funciones de exportación del sistema).
              </li>
              <li>
                <strong>Confidencialidad:</strong> recibir tratamiento confidencial de sus datos.
              </li>
            </ul>
            <p>
              Las solicitudes deben enviarse a{' '}
              <a
                href="mailto:julietaarrazate@gmail.com"
                className="text-violet-600 dark:text-violet-400 hover:underline"
              >
                julietaarrazate@gmail.com
              </a>{' '}
              con asunto "Solicitud Ley 25.326", acreditando la identidad del solicitante.
              Se responderá en un plazo máximo de 5 días hábiles.
            </p>
            <p className="text-sm text-gray-500 dark:text-zinc-400">
              La <strong>Agencia de Acceso a la Información Pública (AAIP)</strong>, en su
              carácter de Órgano de Control de la Ley 25.326, tiene la atribución de atender
              denuncias y reclamos sobre incumplimiento de las normas de protección de datos
              personales.
            </p>
          </Section>

          <Section title="11. Seguridad">
            <p>Cuadra implementa las siguientes medidas técnicas y organizativas:</p>
            <ul>
              <li>Contraseñas almacenadas con hash irreversible (pbkdf2_sha256).</li>
              <li>Comunicaciones cifradas mediante TLS/HTTPS en todos los endpoints.</li>
              <li>Autenticación por token JWT con expiración de 8 horas.</li>
              <li>Verificación en dos pasos por email para roles de administración.</li>
              <li>Rate limiting en endpoints de autenticación.</li>
              <li>Control de acceso por roles (superadmin, admin, operador, revisor, contador).</li>
              <li>Registros de auditoría de acceso y operaciones.</li>
              <li>Backups cifrados diarios enviados por correo electrónico.</li>
            </ul>
          </Section>

          <Section title="12. Cookies y tecnologías similares">
            <p>
              Cuadra no utiliza cookies de rastreo ni publicidad. Utiliza{' '}
              <code>localStorage</code> del navegador para almacenar el token de sesión JWT
              y preferencias de interfaz (tema, organización activa). Estos datos no se
              transmiten a terceros ni se usan con fines de perfilado.
            </p>
          </Section>

          <Section title="13. Cambios a esta política">
            <p>
              Cualquier modificación será notificada al correo registrado con al menos 7 días
              de anticipación. La versión vigente es la publicada en esta URL. El uso continuado
              del sistema implica la aceptación de los términos vigentes.
            </p>
          </Section>

          <Section title="14. Contacto">
            <p>
              Para consultas sobre esta política o para ejercer derechos sobre datos personales:{' '}
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
