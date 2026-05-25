import React from 'react'
import { useConfirmStore } from '@/store/confirm'
import { ConfirmModal } from './ConfirmModal'

export const ConfirmDialog: React.FC = () => {
  const { open, title, message, confirmLabel, cancelLabel, danger, close } = useConfirmStore()
  return (
    <ConfirmModal
      open={open}
      title={title}
      message={message ?? ''}
      confirmLabel={confirmLabel}
      cancelLabel={cancelLabel}
      danger={danger}
      onConfirm={() => close(true)}
      onCancel={() => close(false)}
    />
  )
}
