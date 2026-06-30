# Política de Seguridad

Cuadra maneja datos financieros de empresas y sus clientes. La seguridad es prioritaria.

## Reportar una vulnerabilidad

Si encontrás una vulnerabilidad, **no abras un issue público**. Reportala de forma privada a:

**julietaarrazate@gmail.com**

Incluí: descripción, pasos para reproducir, impacto estimado y, si podés, una sugerencia de
mitigación. Te respondemos a la brevedad y coordinamos la divulgación responsable.

## Alcance

Reportes válidos incluyen, entre otros: bypass de autenticación/permisos, fuga de datos entre
organizaciones (multi-tenant), inyección, exposición de secretos, escalación de privilegios.

## Modelo de seguridad

El diseño de seguridad (auth JWT, hashing `pbkdf2_sha256`, roles y permisos, aislamiento
multi-tenant, 2FA, rate limiting, cifrado de certificados ARCA, headers) está documentado en
[`docs/security/SECURITY_MODEL.md`](docs/security/SECURITY_MODEL.md).

## Buenas prácticas para contribuir

- Nunca commitear secretos/keys (viven en env vars de Render/Vercel).
- Respetar el aislamiento por `organizacion_id` en todo endpoint.
- Validar inputs y archivos subidos (magic bytes).
- Ver el [security checklist](.claude/checklists/security_checklist.md) antes de mergear cambios
  sensibles.
