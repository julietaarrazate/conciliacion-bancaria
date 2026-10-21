import { describe, it, expect } from 'vitest'
import { manejaVariasOrgs } from '../orgs'

describe('manejaVariasOrgs', () => {
  it('superadmin sí', () => expect(manejaVariasOrgs({ is_superadmin: true })).toBe(true))
  it('con organizaciones extra sí', () => expect(manejaVariasOrgs({ is_superadmin: false, allowed_org_ids: [2] })).toBe(true))
  it('una sola organización no', () => {
    expect(manejaVariasOrgs({ is_superadmin: false, allowed_org_ids: [] })).toBe(false)
    expect(manejaVariasOrgs({ is_superadmin: false })).toBe(false)
    expect(manejaVariasOrgs(null)).toBe(false)
  })
})
