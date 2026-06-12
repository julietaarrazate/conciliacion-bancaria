import React from 'react'
import { emptyForm, fmt } from '@/components/cheques/shared'
import { useCheques } from '@/components/cheques/useCheques'
import { ChequesTabTodos } from '@/components/cheques/ChequesTabTodos'
import { ChequesTabDeposito } from '@/components/cheques/ChequesTabDeposito'
import { ChequesTabRechazados } from '@/components/cheques/ChequesTabRechazados'
import { ChequesTabMasiva } from '@/components/cheques/ChequesTabMasiva'
import { ModalCheque } from '@/components/cheques/ModalCheque'
import { ModalAcreditar } from '@/components/cheques/ModalAcreditar'
import { ModalRechazar } from '@/components/cheques/ModalRechazar'

export const Cheques: React.FC = () => {
  const c = useCheques()

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Cheques</h1>
          <p className="text-xs text-gray-500 mt-0.5">Registro y seguimiento de cheques de terceros</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <input ref={c.importRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={c.handleImportExcel} />
          <button onClick={() => c.importRef.current?.click()} disabled={c.importando}
            className="px-3 py-1.5 bg-gray-100 dark:bg-white/8 hover:bg-gray-200 dark:hover:bg-white/12 text-gray-700 dark:text-gray-300 text-sm rounded-lg transition-colors disabled:opacity-50">
            {c.importando ? 'Importando…' : '↑ Importar Excel'}
          </button>
          <button onClick={c.handleExportarTodos} disabled={c.exportandoTodos}
            className="px-3 py-1.5 bg-green-100 hover:bg-green-200 dark:bg-green-700/30 dark:hover:bg-green-700/50 text-green-700 dark:text-green-400 text-sm rounded-lg transition-colors disabled:opacity-50">
            {c.exportandoTodos ? 'Exportando…' : '↓ Excel'}
          </button>
          <button onClick={() => { c.setEditId(null); c.setShowForm(true); c.setFormData(emptyForm()); c.setFormFoto(null); c.setMsg('') }}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors">
            + Nuevo cheque
          </button>
        </div>
      </div>

      {c.msg && (
        <div className={`text-sm rounded-lg px-3 py-2 border ${c.msg.startsWith('✓') ? 'text-green-700 bg-green-50 border-green-200 dark:text-green-400 dark:bg-green-500/10 dark:border-green-500/20' : 'text-red-700 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-500/10 dark:border-red-500/20'}`}>
          {c.msg}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Pendientes',  value: fmt(c.totalPend),  sub: `${c.pendientes.length} cheq.`, color: 'text-yellow-600 dark:text-yellow-400' },
          { label: 'Acreditados', value: fmt(c.totalAcred), sub: 'en el listado',                color: 'text-green-600 dark:text-green-400'  },
          { label: 'Rechazados',  value: fmt(c.totalRech),  sub: 'en el listado',                color: 'text-red-600 dark:text-red-400'    },
        ].map(s => (
          <div key={s.label} className="bg-white dark:bg-white/3 border border-gray-200 dark:border-white/8 rounded-xl p-3 overflow-hidden">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-sm font-semibold mt-1 truncate ${s.color}`}>{s.value}</p>
            <p className="text-xs text-gray-600 mt-0.5">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-white/8">
        {(['todos', 'deposito', 'rechazados', 'masiva'] as const).map(t => (
          <button key={t} onClick={() => c.setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              c.tab === t ? 'border-indigo-600 text-indigo-600 dark:border-indigo-500 dark:text-indigo-400' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}>
            {t === 'todos' ? 'Todos' : t === 'deposito' ? 'Por depósito' : t === 'rechazados' ? 'Rechazados' : '📷 Carga masiva'}
          </button>
        ))}
      </div>

      {c.tab === 'todos' && (
        <ChequesTabTodos
          cheques={c.cheques} clientes={c.clientes} loading={c.loading} total={c.total} skip={c.skip} limit={c.LIMIT} canDelete={c.canDelete}
          filtroEstado={c.filtroEstado} filtroCliente={c.filtroCliente} filtroDesde={c.filtroDesde} filtroHasta={c.filtroHasta}
          onFiltroEstado={v => { c.setFiltroEstado(v); c.setSkip(0) }}
          onFiltroCliente={v => { c.setFiltroCliente(v); c.setSkip(0) }}
          onFiltroDesde={v => { c.setFiltroDesde(v); c.setSkip(0) }}
          onFiltroHasta={v => { c.setFiltroHasta(v); c.setSkip(0) }}
          onLimpiarFiltros={() => { c.setFiltroEstado(''); c.setFiltroCliente(''); c.setFiltroDesde(''); c.setFiltroHasta(''); c.setSkip(0) }}
          onSkipChange={c.setSkip}
          onVerFoto={c.handleVerFoto}
          onCompartir={c.handleCompartir}
          onEdit={c.handleOpenEdit}
          onAcreditar={id => { c.setAcreditarId(id); c.setAcreditarFecha(''); c.setAcreditarBancoId('') }}
          onRechazar={id => { c.setRechazarId(id); c.setRechazarData({ fecha_rechazo: '', gastos_bancarios: '', fisico: false, fecha_devolucion: '' }) }}
          onDelete={c.handleDelete}
        />
      )}

      {c.tab === 'deposito' && (
        <ChequesTabDeposito
          depositoFechas={c.depositoFechas} depositoFecha={c.depositoFecha} depositoData={c.depositoData}
          depositoLoading={c.depositoLoading} exportandoDeposito={c.exportandoDeposito} bancoCuentas={c.bancoCuentas}
          selectedCheques={c.selectedCheques} acredMasivoBanco={c.acredMasivoBanco} acredMasivoFecha={c.acredMasivoFecha}
          acreditandoMasivo={c.acreditandoMasivo}
          onDepositoFechaChange={c.setDepositoFecha}
          onExportDeposito={c.handleExportDeposito}
          onAcredMasivoBanco={c.setAcredMasivoBanco}
          onAcredMasivoFecha={c.setAcredMasivoFecha}
          onAcreditarMasivo={c.handleAcreditarMasivo}
          onSetSelected={c.setSelectedCheques}
        />
      )}

      {c.tab === 'rechazados' && (
        <ChequesTabRechazados rechazadosList={c.rechazadosList} rechazadosLoading={c.rechazadosLoading} />
      )}

      {c.tab === 'masiva' && (
        <ChequesTabMasiva
          clientes={c.clientes} bulkFiles={c.bulkFiles} bulkPreviews={c.bulkPreviews} bulkRows={c.bulkRows}
          bulkProcessing={c.bulkProcessing} bulkSaving={c.bulkSaving} bulkMsg={c.bulkMsg} bulkInputRef={c.bulkInputRef}
          onFileChange={c.handleBulkFileChange}
          onRemoveFile={c.handleBulkRemoveFile}
          onProcess={c.handleBulkProcess}
          onUpdateRow={c.handleBulkUpdateRow}
          onRemoveRow={c.handleBulkRemoveRow}
          onClearRows={c.clearBulkRows}
          onSave={c.handleBulkSave}
        />
      )}

      {c.showForm && (
        <ModalCheque
          editId={c.editId} formData={c.formData} formFoto={c.formFoto} saving={c.saving} msg={c.msg}
          clientes={c.clientes} portadores={c.portadores} fotoInputRef={c.fotoInputRef}
          onClose={() => { c.setShowForm(false); c.setEditId(null) }}
          onChange={fn => c.setFormData(fn)}
          onSave={c.handleSave}
          onAddCliente={c.handleAddCliente}
          onAddPortador={c.handleAddPortador}
          onFotoChange={c.handleFotoChange}
          onRemoveFoto={() => c.setFormFoto(null)}
        />
      )}

      {c.acreditarId && (
        <ModalAcreditar
          bancoCuentas={c.bancoCuentas} acreditarBancoId={c.acreditarBancoId} acreditarFecha={c.acreditarFecha} actioning={c.actioning}
          onBancoChange={c.setAcreditarBancoId}
          onFechaChange={c.setAcreditarFecha}
          onCancel={() => c.setAcreditarId(null)}
          onConfirm={c.handleAcreditar}
        />
      )}

      {c.rechazarId && (
        <ModalRechazar
          rechazarData={c.rechazarData} actioning={c.actioning}
          onChange={fn => c.setRechazarData(fn)}
          onCancel={() => c.setRechazarId(null)}
          onConfirm={c.handleRechazar}
        />
      )}

      {/* ═══ Modal: Ver foto ═══ */}
      {c.verFotoId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => { c.setVerFotoId(null); c.setFotoData(null) }}>
          <div className="bg-white dark:bg-[#16161A] border border-gray-200 dark:border-white/10 rounded-xl p-4 max-w-lg w-full" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Comprobante del cheque</h2>
              <button onClick={() => { c.setVerFotoId(null); c.setFotoData(null) }} className="text-gray-500 hover:text-gray-700 dark:text-gray-300 text-xl">×</button>
            </div>
            {c.loadingFoto ? (
              <div className="text-center py-8 text-gray-400 text-sm">Cargando imagen…</div>
            ) : c.fotoData ? (
              <>
                <img src={c.fotoData} alt="comprobante" className="w-full rounded-lg object-contain max-h-[60vh]" />
                <button
                  onClick={() => {
                    const ch = c.cheques.find(x => x.id === c.verFotoId) || c.rechazadosList.find(x => x.id === c.verFotoId)
                    if (ch) c.handleCompartir(ch)
                  }}
                  className="mt-3 w-full py-2 bg-green-100 hover:bg-green-200 dark:bg-green-600/20 dark:hover:bg-green-600/30 text-green-700 dark:text-green-400 rounded-lg text-sm transition-colors">
                  📤 Compartir por WhatsApp
                </button>
              </>
            ) : (
              <div className="text-center py-8 text-gray-500 text-sm">No se pudo cargar la imagen</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
