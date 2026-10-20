/**
 * ¿El usuario maneja más de una organización? (superadmin, o un contador con
 * organizaciones extra en `allowed_org_ids`). Decide si se muestran el selector
 * de organización y las vistas que cruzan organizaciones (Procesos masivos).
 * Una organización es una empresa que usa Cuadra; sus clientes son otra cosa.
 */
export function manejaVariasOrgs(user: { is_superadmin?: boolean; allowed_org_ids?: number[] | null } | null | undefined): boolean {
  return !!user && (!!user.is_superadmin || (user.allowed_org_ids?.length ?? 0) > 0)
}
