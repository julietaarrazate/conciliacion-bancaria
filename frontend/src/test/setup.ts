// Setup global de Vitest: matchers de jest-dom (toBeInTheDocument, etc.)
// y limpieza del DOM entre tests.
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})
