import React, { useEffect, useMemo, useState } from 'react'
import { apiClient } from '@/services/api'
import { Proveedor } from '@/types'

interface CampoProveedorProps {
  id: string
  value: string
  orgId?: number | null
  className?: string
  placeholder?: string
  onChange: (valor: string) => void
  /** Proveedor de la ficha que coincide con el nombre escrito (o null). */
  onProveedorChange: (proveedorId: number | null) => void
}

const normalizar = (s: string) => s.trim().toLocaleLowerCase('es-AR')

/**
 * Nombre de un proveedor PROPIO de la organización, con sugerencias de la
 * ficha de proveedores. Si el nombre coincide con uno de la ficha, el pago se
 * vincula a él; si no, se registra igual con el nombre escrito.
 * No usar en OP por cuenta de un cliente (esos son proveedores del cliente).
 */
export const CampoProveedor: React.FC<CampoProveedorProps> = ({
  id, value, orgId, className = 'input-field', placeholder, onChange, onProveedorChange,
}) => {
  const [proveedores, setProveedores] = useState<Proveedor[]>([])

  useEffect(() => {
    let cancelado = false
    apiClient.listarProveedores(orgId).then(p => { if (!cancelado) setProveedores(p) }).catch(() => {})
    return () => { cancelado = true }
  }, [orgId])

  const elegido = useMemo(
    () => proveedores.find(p => normalizar(p.razon_social) === normalizar(value)) || null,
    [proveedores, value],
  )
  const elegidoId = elegido?.id ?? null
  useEffect(() => { onProveedorChange(elegidoId) }, [elegidoId]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <input id={id} className={className} value={value} placeholder={placeholder}
        list={`${id}-lista`} autoComplete="off" onChange={e => onChange(e.target.value)} />
      <datalist id={`${id}-lista`}>
        {proveedores.map(p => <option key={p.id} value={p.razon_social}>{p.cuit || ''}</option>)}
      </datalist>
      {elegido && (
        <p className="mt-1 text-[11px] text-ml-green">
          ✓ De la ficha de proveedores{elegido.cuit ? ` · CUIT ${elegido.cuit}` : ''}
        </p>
      )}
    </>
  )
}
