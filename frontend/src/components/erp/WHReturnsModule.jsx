/**
 * Return & Refund — Portal Gudang (Blueprint §3.7)
 *
 * Tipe 1: Expedition Return   — paket kembali dari ekspedisi
 * Tipe 2: Customer Refund     — customer request refund marketplace
 *
 * Workflow: Pending → Received (unboxing) → Inspected → Resolved
 *
 * Tabs:
 *   Dashboard  — stats + action-needed list
 *   Tipe 1     — expedition_return view
 *   Tipe 2     — customer_refund view
 *   Semua      — all returns tabel
 */

import { useState, useEffect, useCallback } from 'react';
import SmartNativeSelect from '@/components/ui/smart-native-select';
import PaginationLite, { useClientPagination } from '@/components/ui/pagination-lite';
import {
  Package, Plus, Search, X, RefreshCw, Eye, CheckCircle,
  Clock, AlertTriangle, Truck, RotateCcw, ChevronRight,
  ChevronDown, FileText, ArrowRight, PackageOpen, CheckSquare,
  XCircle, ShieldAlert, Star, Send, Trash2, MoreVertical,
  ClipboardCheck, PackageCheck
} from 'lucide-react';
import OnwardCTA from './OnwardCTA';
import { formatRupiah } from '@/lib/format';
// F15-B — kelas Tailwind tidak boleh dirakit saat berjalan; lihat lib/tone.js
import { tone } from '@/lib/tone';

const API = process.env.REACT_APP_BACKEND_URL || '';

const CHANNELS   = ['Shopee', 'Tokopedia', 'TikTok Shop', 'Lazada', 'Instagram', 'WhatsApp', 'Lainnya'];
const CONDITIONS = ['Baik', 'Rusak Ringan', 'Rusak Berat', 'Tidak Layak Jual'];
const CAUSES     = ['Kesalahan Gudang', 'Kesalahan Customer', 'Kesalahan Ekspedisi', 'Lainnya'];
const ACTIONS    = ['Restock ke Gudang', 'Reshipment', 'Appeal Platform', 'Dibuang / Dispose', 'Donasi'];
const APPEAL_STATUSES = ['Pending', 'Success', 'Fail'];

const TYPE_LABELS = {
  expedition_return: 'Tipe 1 — Ekspedisi',
  customer_refund:   'Tipe 2 — Customer',
};
const TYPE_COLORS = {
  expedition_return: 'text-orange-600 dark:text-orange-400 bg-orange-100 dark:bg-orange-500/10',
  customer_refund:   'text-violet-600 dark:text-violet-400 bg-violet-100 dark:bg-violet-500/10',
};
const STATUS_COLORS = {
  Pending:   'text-amber-700 dark:text-amber-400 bg-amber-100 dark:bg-amber-500/10',
  Received:  'text-sky-600 dark:text-sky-400 bg-sky-100 dark:bg-sky-500/10',
  Inspected: 'text-violet-600 dark:text-violet-400 bg-violet-100 dark:bg-violet-500/10',
  Resolved:  'text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-500/10',
  Cancelled: 'text-muted-foreground bg-muted dark:bg-slate-500/10',
};
const CONDITION_COLORS = {
  'Baik':              'text-emerald-600 dark:text-emerald-400',
  'Rusak Ringan':      'text-amber-700 dark:text-amber-400',
  'Rusak Berat':       'text-orange-600 dark:text-orange-400',
  'Tidak Layak Jual':  'text-red-700 dark:text-red-400',
};
const CAUSE_COLORS = {
  'Kesalahan Gudang':     'text-red-700 dark:text-red-400',
  'Kesalahan Customer':   'text-amber-700 dark:text-amber-400',
  'Kesalahan Ekspedisi':  'text-orange-600 dark:text-orange-400',
  'Lainnya':              'text-muted-foreground',
};

function Badge({ label, colorClass }) {
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colorClass || 'text-muted-foreground bg-secondary'}`}>{label}</span>;
}

function fmtDate(iso) {
  if (!iso) return '-';
  try { return new Date(iso).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); }
  catch { return iso?.slice(0, 16) || '-'; }
}
function fmtDateShort(iso) {
  if (!iso) return '-';
  try { return new Date(iso).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' }); }
  catch { return iso?.slice(0, 10) || '-'; }
}
const fmtCurrency = formatRupiah;

async function api(method, path, token, body) {
  const opts = { method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(`${API}${path}`, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
}

// ─── WORKFLOW PROGRESS BAR ────────────────────────────────────────────────────
const STEPS = ['Pending', 'Received', 'Inspected', 'Resolved'];
function WorkflowBar({ status }) {
  const idx = STEPS.indexOf(status);
  if (status === 'Cancelled') return <span className="text-xs text-muted-foreground">Dibatalkan</span>;
  return (
    <div className="flex items-center gap-1">
      {STEPS.map((s, i) => (
        <div key={s} className="flex items-center gap-1">
          <div className={`w-2 h-2 rounded-full ${i <= idx ? 'bg-primary' : 'bg-foreground/10'}`} />
          {i < STEPS.length - 1 && <div className={`w-6 h-px ${i < idx ? 'bg-primary' : 'bg-foreground/10'}`} />}
        </div>
      ))}
      <span className="text-xs ml-1 text-muted-foreground">{status}</span>
    </div>
  );
}

// ─── RETURN CARD (list row) ───────────────────────────────────────────────────
function ReturnRow({ ret, onView, onDelete }) {
  return (
    <tr className="border-b border-border hover:bg-foreground/[0.02] cursor-pointer" onClick={() => onView(ret)} data-testid={`ret-row-${ret.id}`}>
      <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{ret.return_code}</td>
      <td className="px-4 py-3">
        <Badge label={TYPE_LABELS[ret.return_type]} colorClass={TYPE_COLORS[ret.return_type]} />
      </td>
      <td className="px-4 py-3 font-medium text-sm">{ret.order_number || ret.resi_number || '-'}</td>
      <td className="px-4 py-3 text-sm text-muted-foreground">{ret.customer_name || '-'}</td>
      <td className="px-4 py-3 text-sm">{ret.product_name || ret.sku_code || '-'}</td>
      <td className="px-4 py-3"><Badge label={ret.status} colorClass={STATUS_COLORS[ret.status]} /></td>
      <td className="px-4 py-3 text-xs text-muted-foreground">{fmtDateShort(ret.created_at)}</td>
      <td className="px-4 py-3 text-right">
        <div className="flex items-center justify-end gap-1">
          <button onClick={e => { e.stopPropagation(); onView(ret); }} className="p-1 hover:bg-foreground/5 rounded" data-testid={`view-ret-${ret.id}`}>
            <Eye className="w-4 h-4 text-muted-foreground" />
          </button>
          {ret.status === 'Pending' && (
            <button onClick={e => { e.stopPropagation(); onDelete(ret); }} className="p-1 hover:bg-red-100 dark:bg-red-500/10 rounded">
              <Trash2 className="w-4 h-4 text-red-700 dark:text-red-400" />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

// ─── CREATE FORM MODAL ────────────────────────────────────────────────────────
function CreateModal({ onClose, onSaved, token, defaultType }) {
  const [form, setForm] = useState({
    return_type: defaultType || 'expedition_return',
    order_number: '', resi_number: '', channel: '',
    customer_name: '', customer_contact: '',
    sku_code: '', product_name: '', qty: 1,
    order_value: 0, initial_reason: '', notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (!form.order_number && !form.resi_number) { setErr('Nomor order atau resi wajib diisi'); return; }
    setSaving(true); setErr('');
    try {
      const ret = await api('POST', '/api/wh/returns', token, form);
      onSaved(ret);
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 bg-foreground/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[var(--card-surface)] rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-4">Catat Return Baru</h3>
        <div className="space-y-3">
          {/* Type */}
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Tipe Return *</label>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(TYPE_LABELS).map(([v, l]) => (
                <button key={v} onClick={() => setForm({ ...form, return_type: v })}
                  className={`py-2 px-3 rounded-lg border text-sm transition ${form.return_type === v ? 'border-primary bg-primary/10 text-primary' : 'border-border hover:bg-foreground/5 text-muted-foreground'}`}
                  data-testid={`type-btn-${v}`}>
                  {l}
                </button>
              ))}
            </div>
          </div>

          {/* Info identifikasi */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">No. Order</label>
              <input value={form.order_number} onChange={e => setForm({ ...form, order_number: e.target.value })}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="SPX-00001" data-testid="ret-order-number" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">No. Resi</label>
              <input value={form.resi_number} onChange={e => setForm({ ...form, resi_number: e.target.value })}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="JNE-123456" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Channel</label>
              <select value={form.channel} onChange={e => setForm({ ...form, channel: e.target.value })}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" data-testid="ret-channel">
                <option value="">Pilih...</option>
                {CHANNELS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Nama Customer</label>
              <input value={form.customer_name} onChange={e => setForm({ ...form, customer_name: e.target.value })}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="Nama customer" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">SKU / Kode Produk</label>
              <input value={form.sku_code} onChange={e => setForm({ ...form, sku_code: e.target.value })}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="DA-001-S-BLK" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Nama Produk</label>
              <input value={form.product_name} onChange={e => setForm({ ...form, product_name: e.target.value })}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="Kemeja Hitam S" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Qty</label>
              <input type="number" min="1" value={form.qty} onChange={e => setForm({ ...form, qty: +e.target.value })}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Nilai Order</label>
              <input type="number" min="0" value={form.order_value} onChange={e => setForm({ ...form, order_value: +e.target.value })}
                className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="0" />
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Alasan Return (Awal)</label>
            <textarea value={form.initial_reason} onChange={e => setForm({ ...form, initial_reason: e.target.value })} rows="2"
              className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)] resize-none"
              placeholder="Barang tidak sampai / ukuran tidak sesuai / dll..." data-testid="ret-reason" />
          </div>
          {err && <div className="text-xs text-red-700 dark:text-red-400">{err}</div>}
        </div>
        <div className="flex gap-3 mt-5">
          <button onClick={onClose} className="flex-1 py-2 border border-border rounded-lg text-sm hover:bg-foreground/5">Batal</button>
          <button onClick={submit} disabled={saving} className="flex-1 py-2 bg-primary text-foreground rounded-lg text-sm hover:brightness-110 disabled:opacity-50" data-testid="save-return-btn">
            {saving ? 'Menyimpan...' : 'Catat Return'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── DETAIL PANEL (full workflow) ─────────────────────────────────────────────
function DetailPanel({ ret, token, onClose, onRefresh, onNavigate }) {
  const [data, setData] = useState(ret);
  const [step, setStep] = useState(null); // 'receive' | 'inspect' | 'resolve' | 'cancel'
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const reload = async () => {
    try {
      const d = await api('GET', `/api/wh/returns/${ret.id}`, token);
      setData(d);
    } catch {}
  };

  const openStep = (s) => { setStep(s); setForm({}); setErr(''); };

  const doReceive = async () => {
    if (!form.unboxing_condition_notes) { setErr('Catatan unboxing wajib diisi'); return; }
    setSaving(true); setErr('');
    try {
      const d = await api('POST', `/api/wh/returns/${data.id}/receive`, token, form);
      setData(d); setStep(null); onRefresh();
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  };

  const doInspect = async () => {
    if (!form.item_condition || !form.return_cause) { setErr('Kondisi item dan penyebab wajib diisi'); return; }
    setSaving(true); setErr('');
    try {
      const d = await api('POST', `/api/wh/returns/${data.id}/inspect`, token, form);
      setData(d); setStep(null); onRefresh();
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  };

  const doResolve = async () => {
    if (!form.action_taken) { setErr('Aksi wajib dipilih'); return; }
    setSaving(true); setErr('');
    try {
      const d = await api('POST', `/api/wh/returns/${data.id}/resolve`, token, form);
      setData(d); setStep(null); onRefresh();
    } catch (e) { setErr(e.message); }
    finally { setSaving(false); }
  };

  const doCancel = async () => {
    if (!window.confirm('Batalkan return ini?')) return;
    setSaving(true);
    try {
      const d = await api('POST', `/api/wh/returns/${data.id}/cancel`, token, { reason: form.reason || 'Dibatalkan manual' });
      setData(d); setStep(null); onRefresh();
    } catch (e) { alert(e.message); }
    finally { setSaving(false); }
  };

  const isEditable = !['Resolved', 'Cancelled'].includes(data.status);

  return (
    <div className="fixed inset-0 bg-foreground/40 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="bg-[var(--card-surface)] rounded-t-2xl sm:rounded-2xl shadow-xl w-full sm:max-w-2xl max-h-[92vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="sticky top-0 bg-[var(--card-surface)] border-b border-border px-6 py-4 flex items-start justify-between z-10 rounded-t-2xl">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-lg font-bold">{data.return_code}</h3>
              <Badge label={TYPE_LABELS[data.return_type]} colorClass={TYPE_COLORS[data.return_type]} />
              <Badge label={data.status} colorClass={STATUS_COLORS[data.status]} />
            </div>
            <WorkflowBar status={data.status} />
          </div>
          <button onClick={onClose} className="p-2 hover:bg-foreground/5 rounded-lg"><X className="w-5 h-5" /></button>
        </div>

        <div className="px-6 py-4 space-y-5">
          {/* Info Utama */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            {[
              { label: 'No. Order', val: data.order_number || '-' },
              { label: 'No. Resi', val: data.resi_number || '-' },
              { label: 'Channel', val: data.channel || '-' },
              { label: 'Customer', val: data.customer_name || '-' },
              { label: 'Produk', val: data.product_name || data.sku_code || '-' },
              { label: 'Qty', val: `${data.qty} pcs` },
              { label: 'Nilai Order', val: fmtCurrency(data.order_value) },
              { label: 'Dicatat Tgl', val: fmtDateShort(data.created_at) },
              { label: 'Oleh', val: data.created_by },
            ].map(f => (
              <div key={f.label}>
                <div className="text-xs text-muted-foreground">{f.label}</div>
                <div className="font-medium mt-0.5">{f.val}</div>
              </div>
            ))}
          </div>
          {data.initial_reason && (
            <div className="bg-foreground/[0.03] rounded-xl p-3">
              <div className="text-xs text-muted-foreground mb-1">Alasan Awal</div>
              <div className="text-sm">{data.initial_reason}</div>
            </div>
          )}

          {/* Step: Received */}
          {data.status !== 'Pending' && (
            <div className="bg-sky-100 dark:bg-sky-500/5 border border-sky-300 dark:border-sky-500/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <PackageOpen className="w-4 h-4 text-sky-600 dark:text-sky-400" />
                <span className="text-sm font-semibold text-sky-600 dark:text-sky-400">Penerimaan & Unboxing</span>
                <span className="text-xs text-muted-foreground ml-auto">{fmtDate(data.received_at)} · {data.received_by}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                <div><span className="text-muted-foreground">Kondisi Kemasan:</span> <span className="ml-1">{data.package_condition || '-'}</span></div>
                <div><span className="text-muted-foreground">Bukti Foto/Video:</span> <span className="ml-1">{data.unboxing_photo_notes || '-'}</span></div>
                <div className="sm:col-span-2"><span className="text-muted-foreground">Catatan Unboxing:</span> <span className="ml-1">{data.unboxing_condition_notes}</span></div>
              </div>
            </div>
          )}

          {/* Step: Inspected */}
          {['Inspected', 'Resolved'].includes(data.status) && (
            <div className="bg-violet-100 dark:bg-violet-500/5 border border-violet-300 dark:border-violet-500/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <ClipboardCheck className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                <span className="text-sm font-semibold text-violet-600 dark:text-violet-400">Hasil Inspeksi</span>
                <span className="text-xs text-muted-foreground ml-auto">{fmtDate(data.inspected_at)} · {data.inspected_by}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground">Kondisi Item:</span>
                  <span className={`ml-1 font-medium ${CONDITION_COLORS[data.item_condition] || ''}`}>{data.item_condition || '-'}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Penyebab:</span>
                  <span className={`ml-1 font-medium ${CAUSE_COLORS[data.return_cause] || ''}`}>{data.return_cause || '-'}</span>
                </div>
                {data.cause_detail && <div className="sm:col-span-2"><span className="text-muted-foreground">Detail:</span> <span className="ml-1">{data.cause_detail}</span></div>}
                <div><span className="text-muted-foreground">Rekomendasi:</span> <span className="ml-1 font-medium">{data.recommended_action || '-'}</span></div>
              </div>
            </div>
          )}

          {/* Step: Resolved */}
          {data.status === 'Resolved' && (
            <div className="bg-emerald-100 dark:bg-emerald-500/5 border border-emerald-300 dark:border-emerald-500/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <PackageCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">Resolusi</span>
                <span className="text-xs text-muted-foreground ml-auto">{fmtDate(data.resolved_at)} · {data.resolved_by}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                <div><span className="text-muted-foreground">Aksi:</span> <span className="ml-1 font-medium">{data.action_taken}</span></div>
                {data.reshipment_resi && <div><span className="text-muted-foreground">Resi Reshipment:</span> <span className="ml-1 font-mono">{data.reshipment_resi}</span></div>}
                {data.appeal_status && <div><span className="text-muted-foreground">Status Appeal:</span> <span className="ml-1">{data.appeal_status}</span></div>}
                {data.restock_qty > 0 && <div><span className="text-muted-foreground">Qty Restock:</span> <span className="ml-1">{data.restock_qty} pcs</span></div>}
                {data.action_notes && <div className="sm:col-span-2"><span className="text-muted-foreground">Catatan:</span> <span className="ml-1">{data.action_notes}</span></div>}
                {data.source_marketing_return_id && (
                  <div className="sm:col-span-2 pt-1">
                    <span className="text-muted-foreground">Retur Toko asal:</span>
                    <span className="ml-1 font-mono text-xs">{data.source_marketing_return_id.slice(0, 8)}…</span>
                  </div>
                )}
              </div>

              {/* RC-FLOW-UX-11b: retur asal Toko selesai di-restock → CTA balik ke Marketing untuk credit note */}
              {data.source_marketing_return_id && onNavigate && (
                <div className="mt-3">
                  <OnwardCTA
                    onNavigate={onNavigate}
                    title="Barang Sudah di Restock — Langkah Berikutnya"
                    actions={[
                      {
                        module: 'marketing-after-sales',
                        params: { tab: 'returns', return_id: data.source_marketing_return_id },
                        label: 'Terbitkan Credit Note & Refund',
                        primary: true,
                        hint: 'Kembali ke portal Toko untuk menerbitkan credit note',
                        testId: 'onward-issue-credit-note',
                      },
                      {
                        module: 'wms-stock-hub',
                        params: { tab: 'stock' },
                        label: 'Cek Stok FG',
                        hint: 'Verifikasi stok setelah restock',
                        testId: 'onward-check-stock',
                      },
                    ]}
                  />
                </div>
              )}
            </div>
          )}

          {/* Timeline */}
          {(data.timeline || []).length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">Timeline</h4>
              <div className="relative pl-4 space-y-3">
                <div className="absolute left-1.5 top-0 bottom-0 w-px bg-foreground/10" />
                {[...(data.timeline || [])].reverse().map((t, i) => (
                  <div key={i} className="relative flex gap-3">
                    <div className="absolute -left-3 top-1 w-2 h-2 rounded-full bg-primary/60" />
                    <div className="ml-3">
                      <div className="flex items-center gap-2">
                        <Badge label={t.status} colorClass={STATUS_COLORS[t.status]} />
                        <span className="text-xs text-muted-foreground">oleh {t.by} · {fmtDate(t.at)}</span>
                      </div>
                      {t.note && <p className="text-xs text-muted-foreground mt-0.5">{t.note}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          {isEditable && (
            <div className="border-t border-border pt-4">
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">Lanjutkan Proses</h4>
              <div className="flex flex-wrap gap-2">
                {data.status === 'Pending' && (
                  <button onClick={() => openStep('receive')} className="flex items-center gap-2 px-4 py-2 bg-sky-600 text-foreground rounded-lg text-sm hover:brightness-110" data-testid="btn-receive">
                    <PackageOpen className="w-4 h-4" /> Terima Barang (Unboxing)
                  </button>
                )}
                {data.status === 'Received' && (
                  <button onClick={() => openStep('inspect')} className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-foreground rounded-lg text-sm hover:brightness-110" data-testid="btn-inspect">
                    <ClipboardCheck className="w-4 h-4" /> Inspeksi Kondisi
                  </button>
                )}
                {data.status === 'Inspected' && (
                  <button onClick={() => openStep('resolve')} className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-foreground rounded-lg text-sm hover:brightness-110" data-testid="btn-resolve">
                    <CheckCircle className="w-4 h-4" /> Selesaikan (Resolusi)
                  </button>
                )}
                <button onClick={() => openStep('cancel')} className="flex items-center gap-2 px-3 py-2 border border-red-400 dark:border-red-500/30 text-red-700 dark:text-red-400 rounded-lg text-sm hover:bg-red-100 dark:bg-red-500/10">
                  <XCircle className="w-4 h-4" /> Batalkan
                </button>
              </div>
            </div>
          )}

          {/* Inline Step Forms */}

          {/* RECEIVE form */}
          {step === 'receive' && (
            <div className="bg-sky-100 dark:bg-sky-500/5 border border-sky-300 dark:border-sky-500/20 rounded-xl p-4 space-y-3">
              <h4 className="font-semibold text-sky-600 dark:text-sky-400 flex items-center gap-2"><PackageOpen className="w-4 h-4" /> Terima & Unboxing</h4>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Kondisi Kemasan Luar</label>
                <input value={form.package_condition || ''} onChange={e => setForm({ ...form, package_condition: e.target.value })}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="Segel utuh / basah / sobek / dll" />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Kode / Link Bukti Foto/Video Unboxing</label>
                <input value={form.unboxing_photo_notes || ''} onChange={e => setForm({ ...form, unboxing_photo_notes: e.target.value })}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="IMG_001 / Google Drive link / dll" data-testid="unboxing-photo" />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Catatan Kondisi Saat Unboxing *</label>
                <textarea value={form.unboxing_condition_notes || ''} onChange={e => setForm({ ...form, unboxing_condition_notes: e.target.value })} rows="3"
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)] resize-none"
                  placeholder="Barang tampak normal, bungkus dalam sobek, item masih berplastik..." data-testid="unboxing-notes" />
              </div>
              {err && <div className="text-xs text-red-700 dark:text-red-400">{err}</div>}
              <div className="flex gap-2">
                <button onClick={() => setStep(null)} className="px-3 py-1.5 border border-border rounded-lg text-sm hover:bg-foreground/5">Batal</button>
                <button onClick={doReceive} disabled={saving} className="px-4 py-1.5 bg-sky-600 text-foreground rounded-lg text-sm hover:brightness-110 disabled:opacity-50" data-testid="confirm-receive-btn">
                  {saving ? '...' : 'Konfirmasi Terima'}
                </button>
              </div>
            </div>
          )}

          {/* INSPECT form */}
          {step === 'inspect' && (
            <div className="bg-violet-100 dark:bg-violet-500/5 border border-violet-300 dark:border-violet-500/20 rounded-xl p-4 space-y-3">
              <h4 className="font-semibold text-violet-600 dark:text-violet-400 flex items-center gap-2"><ClipboardCheck className="w-4 h-4" /> Inspeksi Kondisi Item</h4>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Kondisi Item *</label>
                  <select value={form.item_condition || ''} onChange={e => setForm({ ...form, item_condition: e.target.value })}
                    className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" data-testid="inspect-condition">
                    <option value="">Pilih...</option>
                    {CONDITIONS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Penyebab Return *</label>
                  <select value={form.return_cause || ''} onChange={e => setForm({ ...form, return_cause: e.target.value })}
                    className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" data-testid="inspect-cause">
                    <option value="">Pilih...</option>
                    {CAUSES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Detail Penyebab</label>
                <input value={form.cause_detail || ''} onChange={e => setForm({ ...form, cause_detail: e.target.value })}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="Jelaskan lebih detail..." />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Rekomendasi Tindakan</label>
                <select value={form.recommended_action || ''} onChange={e => setForm({ ...form, recommended_action: e.target.value })}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" data-testid="inspect-action">
                  <option value="">Auto (dari penyebab)</option>
                  {ACTIONS.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>
              {err && <div className="text-xs text-red-700 dark:text-red-400">{err}</div>}
              <div className="flex gap-2">
                <button onClick={() => setStep(null)} className="px-3 py-1.5 border border-border rounded-lg text-sm hover:bg-foreground/5">Batal</button>
                <button onClick={doInspect} disabled={saving} className="px-4 py-1.5 bg-violet-600 text-foreground rounded-lg text-sm hover:brightness-110 disabled:opacity-50" data-testid="confirm-inspect-btn">
                  {saving ? '...' : 'Simpan Inspeksi'}
                </button>
              </div>
            </div>
          )}

          {/* RESOLVE form */}
          {step === 'resolve' && (
            <div className="bg-emerald-100 dark:bg-emerald-500/5 border border-emerald-300 dark:border-emerald-500/20 rounded-xl p-4 space-y-3">
              <h4 className="font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-2"><CheckCircle className="w-4 h-4" /> Resolusi Return</h4>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Tindakan yang Diambil *</label>
                <select value={form.action_taken || data.recommended_action || ''} onChange={e => setForm({ ...form, action_taken: e.target.value })}
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" data-testid="resolve-action">
                  <option value="">Pilih tindakan...</option>
                  {ACTIONS.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>

              {/* Conditional extra fields */}
              {(form.action_taken || data.recommended_action) === 'Reshipment' && (
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">No. Resi Reshipment</label>
                  <input value={form.reshipment_resi || ''} onChange={e => setForm({ ...form, reshipment_resi: e.target.value })}
                    className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" placeholder="Masukkan resi pengiriman ulang..." data-testid="reshipment-resi" />
                </div>
              )}
              {(form.action_taken || data.recommended_action) === 'Appeal Platform' && (
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Status Appeal</label>
                  <select value={form.appeal_status || ''} onChange={e => setForm({ ...form, appeal_status: e.target.value })}
                    className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" data-testid="appeal-status">
                    <option value="">Pilih...</option>
                    {APPEAL_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              )}
              {(form.action_taken || data.recommended_action) === 'Restock ke Gudang' && (
                <div>
                  <label className="text-xs text-muted-foreground block mb-1">Qty Restock</label>
                  <input type="number" min="1" value={form.restock_qty ?? data.qty} onChange={e => setForm({ ...form, restock_qty: +e.target.value })}
                    className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)]" data-testid="restock-qty" />
                </div>
              )}
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Catatan Resolusi</label>
                <textarea value={form.action_notes || ''} onChange={e => setForm({ ...form, action_notes: e.target.value })} rows="2"
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)] resize-none"
                  placeholder="Catatan tambahan tindakan yang diambil..." />
              </div>
              {err && <div className="text-xs text-red-700 dark:text-red-400">{err}</div>}
              <div className="flex gap-2">
                <button onClick={() => setStep(null)} className="px-3 py-1.5 border border-border rounded-lg text-sm hover:bg-foreground/5">Batal</button>
                <button onClick={doResolve} disabled={saving} className="px-4 py-1.5 bg-emerald-600 text-foreground rounded-lg text-sm hover:brightness-110 disabled:opacity-50" data-testid="confirm-resolve-btn">
                  {saving ? '...' : 'Selesaikan'}
                </button>
              </div>
            </div>
          )}

          {/* CANCEL form */}
          {step === 'cancel' && (
            <div className="bg-red-100 dark:bg-red-500/5 border border-red-300 dark:border-red-500/20 rounded-xl p-4 space-y-3">
              <h4 className="font-semibold text-red-700 dark:text-red-400 flex items-center gap-2"><XCircle className="w-4 h-4" /> Batalkan Return</h4>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">Alasan Pembatalan</label>
                <textarea value={form.reason || ''} onChange={e => setForm({ ...form, reason: e.target.value })} rows="2"
                  className="w-full border border-border rounded-lg px-3 py-2 text-sm bg-[var(--card-surface)] resize-none"
                  placeholder="Kenapa return ini dibatalkan?..." />
              </div>
              <div className="flex gap-2">
                <button onClick={() => setStep(null)} className="px-3 py-1.5 border border-border rounded-lg text-sm hover:bg-foreground/5">Batal</button>
                <button onClick={doCancel} disabled={saving} className="px-4 py-1.5 bg-red-600 text-foreground rounded-lg text-sm hover:brightness-110 disabled:opacity-50" data-testid="confirm-cancel-btn">
                  {saving ? '...' : 'Ya, Batalkan'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── RETURNS TABLE ────────────────────────────────────────────────────────────
function ReturnsTable({ returns, loading, onView, onDelete }) {
  const { page, setPage, totalPages, total, paged } = useClientPagination(returns, 10);
  if (loading) return <div className="text-center py-10 text-muted-foreground">Memuat...</div>;
  if (!returns.length) return <div className="text-center py-10 text-muted-foreground">Belum ada data return</div>;
  return (
    <div className="bg-[var(--card-surface)] rounded-xl border border-border overflow-x-auto">
      <table className="w-full text-sm min-w-[750px]">
        <thead className="bg-[var(--glass-bg)] border-b border-border">
          <tr>
            <th className="text-left px-4 py-3 text-muted-foreground font-medium">Kode</th>
            <th className="text-left px-4 py-3 text-muted-foreground font-medium">Tipe</th>
            <th className="text-left px-4 py-3 text-muted-foreground font-medium">No. Order/Resi</th>
            <th className="text-left px-4 py-3 text-muted-foreground font-medium">Customer</th>
            <th className="text-left px-4 py-3 text-muted-foreground font-medium">Produk</th>
            <th className="text-center px-4 py-3 text-muted-foreground font-medium">Status</th>
            <th className="text-right px-4 py-3 text-muted-foreground font-medium">Tanggal</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {paged.map(r => <ReturnRow key={r.id} ret={r} onView={onView} onDelete={onDelete} />)}
        </tbody>
      </table>
      <PaginationLite page={page} totalPages={totalPages} total={total} onPageChange={setPage} className="px-1" />
    </div>
  );
}

// ─── DASHBOARD TAB ────────────────────────────────────────────────────────────
function DashboardTab({ token, onView, onDelete }) {
  const [summary, setSummary] = useState(null);
  const [actionItems, setActionItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, items] = await Promise.all([
        api('GET', '/api/wh/returns/summary', token),
        // Items yang perlu aksi (Pending + Received + Inspected)
        api('GET', '/api/wh/returns?status=Pending', token).then(d =>
          api('GET', '/api/wh/returns?status=Received', token).then(d2 =>
            api('GET', '/api/wh/returns?status=Inspected', token).then(d3 =>
              [...(Array.isArray(d) ? d : []), ...(Array.isArray(d2) ? d2 : []), ...(Array.isArray(d3) ? d3 : [])]
            )
          )
        )
      ]);
      setSummary(s);
      setActionItems(items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 20));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      {/* Stat cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: 'Total Return', val: summary.total, color: 'slate', icon: Package },
            { label: 'Pending', val: summary.pending, color: 'amber', icon: Clock },
            { label: 'Diterima', val: summary.received, color: 'sky', icon: PackageOpen },
            { label: 'Diinspeksi', val: summary.inspected, color: 'violet', icon: ClipboardCheck },
            { label: 'Selesai', val: summary.resolved, color: 'emerald', icon: CheckCircle },
            { label: 'Perlu Aksi', val: summary.action_needed, color: 'red', icon: AlertTriangle },
          ].map(s => (
            <div key={s.label} className={`border rounded-xl p-3 ${tone(s.color).surface}`}>
              <div className="flex items-center gap-1.5 mb-1">
                <s.icon className={`w-3.5 h-3.5 ${tone(s.color).text}`} />
                <span className="text-xs text-muted-foreground">{s.label}</span>
              </div>
              <div className={`text-2xl font-bold ${tone(s.color).text}`}>{s.val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Type breakdown */}
      {summary && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-orange-100 dark:bg-orange-500/5 border border-orange-300 dark:border-orange-500/20 rounded-xl p-4 flex items-center gap-3">
            <Truck className="w-8 h-8 text-orange-600 dark:text-orange-400" />
            <div>
              <div className="text-xs text-muted-foreground">Tipe 1 — Ekspedisi</div>
              <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">{summary.expedition_returns}</div>
              <div className="text-xs text-muted-foreground">paket kembali dari ekspedisi</div>
            </div>
          </div>
          <div className="bg-violet-100 dark:bg-violet-500/5 border border-violet-300 dark:border-violet-500/20 rounded-xl p-4 flex items-center gap-3">
            <RotateCcw className="w-8 h-8 text-violet-600 dark:text-violet-400" />
            <div>
              <div className="text-xs text-muted-foreground">Tipe 2 — Customer</div>
              <div className="text-2xl font-bold text-violet-600 dark:text-violet-400">{summary.customer_refunds}</div>
              <div className="text-xs text-muted-foreground">customer request refund</div>
            </div>
          </div>
        </div>
      )}

      {/* Perlu Aksi */}
      {actionItems.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-700 dark:text-amber-400" />
            Perlu Tindakan Segera ({actionItems.length})
          </h3>
          <ReturnsTable returns={actionItems} loading={loading} onView={onView} onDelete={onDelete} />
        </div>
      )}

      {!loading && actionItems.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <CheckCircle className="w-12 h-12 mx-auto mb-3 text-emerald-600 dark:text-emerald-400 opacity-50" />
          <p className="font-medium">Semua return sudah ditangani!</p>
          <p className="text-sm">Tidak ada yang perlu tindakan saat ini.</p>
        </div>
      )}
    </div>
  );
}

// ─── ROOT COMPONENT ───────────────────────────────────────────────────────────
export default function WHReturnsModule({ token, onNavigate }) {
  const [tab, setTab]         = useState('dashboard');
  const [returns, setReturns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch]   = useState('');
  const [statusF, setStatusF] = useState('');
  const [selected, setSelected] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createType, setCreateType] = useState(null);

  const load = useCallback(async (type, extra = {}) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (type)           params.set('return_type', type);
      if (extra.status)   params.set('status', extra.status);
      if (extra.search)   params.set('search', extra.search);
      const data = await api('GET', `/api/wh/returns?${params}`, token);
      setReturns(Array.isArray(data) ? data : []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => {
    if (tab === 'expedition') load('expedition_return', { status: statusF, search });
    if (tab === 'customer')   load('customer_refund',   { status: statusF, search });
    if (tab === 'all')        load('', { status: statusF, search });
  }, [tab, statusF, search, load]);

  const onView = (ret) => setSelected(ret);
  const onDelete = async (ret) => {
    if (!window.confirm(`Hapus return ${ret.return_code}?`)) return;
    try { await api('DELETE', `/api/wh/returns/${ret.id}`, token); refreshCurrent(); }
    catch (e) { alert(e.message); }
  };

  const refreshCurrent = () => {
    if (tab === 'expedition') load('expedition_return', { status: statusF, search });
    if (tab === 'customer')   load('customer_refund',   { status: statusF, search });
    if (tab === 'all')        load('', { status: statusF, search });
  };

  const TABS = [
    { id: 'dashboard',  label: 'Dashboard',         icon: BarChartIcon },
    { id: 'expedition', label: 'Tipe 1 — Ekspedisi', icon: Truck },
    { id: 'customer',   label: 'Tipe 2 — Customer',  icon: RotateCcw },
    { id: 'all',        label: 'Semua Return',        icon: Package },
  ];

  // Quick create shortcuts
  const quickCreate = (type) => { setCreateType(type); setShowCreate(true); };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-2xl font-bold">Retur Fisik & Restock (Gudang)</h2>
          <p className="text-muted-foreground text-sm mt-1">Proses fisik: penerimaan barang, inspeksi kondisi, dan resolusi (restock / reshipment / dispose)</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => quickCreate('expedition_return')}
            className="flex items-center gap-2 px-3 py-2 bg-orange-600/10 border border-orange-400 dark:border-orange-500/30 text-orange-600 dark:text-orange-400 rounded-lg text-sm hover:bg-orange-600/20" data-testid="btn-add-expedition">
            <Truck className="w-4 h-4" /> + Tipe 1
          </button>
          <button onClick={() => quickCreate('customer_refund')}
            className="flex items-center gap-2 px-3 py-2 bg-violet-600/10 border border-violet-400 dark:border-violet-500/30 text-violet-600 dark:text-violet-400 rounded-lg text-sm hover:bg-violet-600/20" data-testid="btn-add-customer">
            <RotateCcw className="w-4 h-4" /> + Tipe 2
          </button>
          <button onClick={() => { setCreateType(null); setShowCreate(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-foreground rounded-lg text-sm font-medium hover:brightness-110" data-testid="btn-add-return">
            <Plus className="w-4 h-4" /> Catat Return
          </button>
        </div>
      </div>

      {/* RC-FLOW-UX — onward CTA: setelah barang retur diterima → cek/perbarui stok (Alur 8 selesai) */}
      <OnwardCTA
        onNavigate={onNavigate}
        title="Setelah Barang Retur Diterima"
        actions={[
          { module: 'wms-stock-hub', label: 'Lihat & Sesuaikan Stok', icon: Package, primary: true, hint: 'Barang retur layak jual masuk kembali ke stok' },
        ]}
      />

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-border overflow-x-auto pb-0">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            data-testid={`wh-ret-tab-${t.id}`}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition whitespace-nowrap -mb-px ${
              tab === t.id ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}>
            <t.icon className="w-4 h-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Toolbar (only for non-dashboard tabs) */}
      {tab !== 'dashboard' && (
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex items-center gap-2 border border-border rounded-lg px-3 py-2 bg-[var(--card-surface)] flex-1 min-w-48">
            <Search className="w-4 h-4 text-muted-foreground" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari kode, no. order, resi, customer..."
              className="flex-1 bg-transparent text-sm focus:outline-none" data-testid="wh-ret-search" />
            {search && <button onClick={() => setSearch('')}><X className="w-4 h-4 text-muted-foreground" /></button>}
          </div>
          <SmartNativeSelect value={statusF} onChange={e => setStatusF(e.target.value)} className="border border-border rounded-lg px-3 py-2 bg-[var(--card-surface)] text-sm" data-testid="wh-ret-status-filter">
            <option value="">Semua Status</option>
            {['Pending', 'Received', 'Inspected', 'Resolved', 'Cancelled'].map(s => <option key={s} value={s}>{s}</option>)}
          </SmartNativeSelect>
          <button onClick={refreshCurrent} className="p-2 border border-border rounded-lg hover:bg-foreground/5"><RefreshCw className="w-4 h-4" /></button>
        </div>
      )}

      {/* Tab Content */}
      {tab === 'dashboard'  && <DashboardTab token={token} onView={onView} onDelete={onDelete} />}
      {tab === 'expedition' && <ReturnsTable returns={returns} loading={loading} onView={onView} onDelete={onDelete} />}
      {tab === 'customer'   && <ReturnsTable returns={returns} loading={loading} onView={onView} onDelete={onDelete} />}
      {tab === 'all'        && <ReturnsTable returns={returns} loading={loading} onView={onView} onDelete={onDelete} />}

      {/* Detail Panel */}
      {selected && (
        <DetailPanel ret={selected} token={token} onClose={() => setSelected(null)}
          onRefresh={() => { setSelected(null); refreshCurrent(); }} onNavigate={onNavigate} />
      )}

      {/* Create Modal */}
      {showCreate && (
        <CreateModal token={token} defaultType={createType}
          onClose={() => setShowCreate(false)}
          onSaved={(ret) => { setShowCreate(false); setSelected(ret); refreshCurrent(); }} />
      )}
    </div>
  );
}

// Inline icon
function BarChartIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="12" width="4" height="8" /><rect x="10" y="8" width="4" height="12" /><rect x="17" y="4" width="4" height="16" />
    </svg>
  );
}
