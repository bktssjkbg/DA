/**
 * CuttingOrdersModule — pintu utama Portal Cutting.
 *
 * Satu layar, tiga pekerjaan:
 *   1. Daftar order cutting + filter status/pencarian
 *   2. Buat cutting (pilih kain dari master material, opsional pilih roll fisik)
 *   3. Detail: input progres berulang, selesaikan, batalkan
 *
 * Semua mutasi stok terjadi di backend lewat SSOT gudang — UI hanya melaporkan
 * hasilnya (stok kain turun, stok potongan naik) supaya user melihat efeknya.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Scissors, Plus, RefreshCw, Search, PlayCircle, CheckCircle2, XCircle,
  Trash2, Package, ArrowRight, Layers, AlertCircle, Loader2, History,
} from 'lucide-react';
import { toast } from 'sonner';
import { GlassCard } from '@/components/ui/glass';
import Modal from '../Modal';
import { cuttingApi, StatusPill, fmtNum, fmtRp, fmtDateTime } from './cuttingApi';
import useUomOptions from '../../../hooks/useUomOptions';
import { UomSelect, UomConversionHint } from '../uom/UomPicker';
// FASE H-6 — gulungan WAJIB ditunjuk saat memotong kain yang punya gulungan.
import { previewAllocation, fmtQty } from '../warehouse/rollLines';

const EMPTY_FORM = {
  input_material_id: '',
  location_id: '',
  planned_input_qty: '',
  planned_output_qty: '',
  style_name: '',
  style_sku: '',
  output_color: '',
  output_size: '',
  notes: '',
  roll_ids: [],
};

function Field({ label, children, hint, required }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-foreground/80">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      <div className="mt-1">{children}</div>
      {hint && <span className="text-[11px] text-muted-foreground mt-1 block">{hint}</span>}
    </label>
  );
}

const inputCls =
  'w-full h-9 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary)/0.35)]';

export default function CuttingOrdersModule({ token, onNavigate }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [err, setErr] = useState('');

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [materials, setMaterials] = useState([]);
  const [locations, setLocations] = useState([]);
  const [onlyInStock, setOnlyInStock] = useState(true);
  const [rolls, setRolls] = useState([]);
  const [rollMeta, setRollMeta] = useState({ roll_required: false, total_remaining: 0, uom: '' });
  const [saving, setSaving] = useState(false);

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [prog, setProg] = useState({ input_consumed: '', output_qty: '', waste_qty: '', note: '', roll_id: '', input_uom: '', roll_ids: [] });
  const [acting, setActing] = useState(false);
  // FASE H-6: gulungan yang masih bersisa untuk kain order ini (dimuat saat detail
  // dibuka). `rollRequired` datang dari server — layar tidak menebak sendiri.
  const [detailRolls, setDetailRolls] = useState({ items: [], roll_required: false, total_remaining: 0, uom: '' });

  // ROADMAP P1 (2026-08-05) — operator lantai boleh mencatat pemakaian kain
  // dalam satuan lain (rol/gram/yard); server menerjemahkan ke satuan order.
  const { options: uomOpts } = useUomOptions(detail?.input_material_id ? [detail.input_material_id] : []);
  const progUomOpt = detail?.input_material_id ? uomOpts[detail.input_material_id] : null;
  const orderUnit = String(detail?.input_unit || '').toLowerCase();
  const effProgUom = prog.input_uom || orderUnit;

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setErr('');
    try {
      const qs = new URLSearchParams();
      if (status) qs.set('status', status);
      if (q) qs.set('q', q);
      setRows(await cuttingApi('GET', `/orders${qs.toString() ? `?${qs}` : ''}`, token));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [token, status, q]);

  useEffect(() => { load(); }, [load]);

  const openCreate = async () => {
    setForm(EMPTY_FORM);
    setRolls([]);
    setShowCreate(true);
    try {
      const [mats, locs] = await Promise.all([
        cuttingApi('GET', '/input-materials', token),
        cuttingApi('GET', '/locations', token),
      ]);
      setMaterials(mats);
      setLocations(locs);
    } catch (e) {
      toast.error(`Gagal memuat master kain: ${e.message}`);
    }
  };

  const selectedMaterial = useMemo(
    () => materials.find((m) => m.id === form.input_material_id) || null,
    [materials, form.input_material_id],
  );

  // Stok disimpan PER GUDANG. Dropdown kain menampilkan lokasi yang benar-benar
  // memegang stok agar user tidak membuat cutting di gudang yang kosong
  // (penyebab kegagalan "stok tidak cukup" saat input progres).
  const materialOptions = useMemo(() => {
    const list = onlyInStock ? materials.filter((m) => Number(m.stock_qty || 0) > 0) : materials;
    return list;
  }, [materials, onlyInStock]);

  const onPickMaterial = async (id) => {
    const m = materials.find((x) => x.id === id);
    setForm((f) => ({
      ...f,
      input_material_id: id,
      location_id: m?.best_location_id || '',
      output_color: f.output_color || m?.color || '',
      roll_ids: [],
    }));
    setRolls([]);
    setRollMeta({ roll_required: false, total_remaining: 0, uom: '' });
    if (!id) return;
    try {
      // FASE H-6: respons kini objek ({items, roll_required, total_remaining, uom})
      // supaya layar tahu apakah gulungan WAJIB dan berapa sisa totalnya.
      const res = await cuttingApi('GET', `/rolls?material_id=${id}`, token);
      const items = Array.isArray(res) ? res : (res?.items || []);
      setRolls(items);
      setRollMeta({
        roll_required: !!res?.roll_required,
        total_remaining: Number(res?.total_remaining || 0),
        uom: res?.uom || items[0]?.uom || '',
      });
    } catch {
      setRolls([]);
      setRollMeta({ roll_required: false, total_remaining: 0, uom: '' });
    }
  };

  const stockAtLocation = useMemo(() => {
    if (!selectedMaterial) return null;
    const loc = (selectedMaterial.stock_locations || []).find((l) => l.location_id === form.location_id);
    return loc ? loc.qty : 0;
  }, [selectedMaterial, form.location_id]);

  const submitCreate = async (e) => {
    e.preventDefault();
    if (!form.input_material_id) return toast.error('Pilih material kain dulu.');
    if (!form.style_name.trim()) return toast.error('Nama style/produk wajib diisi.');
    if (!(Number(form.planned_input_qty) > 0)) return toast.error('Rencana pemakaian kain harus > 0.');
    if (!(Number(form.planned_output_qty) > 0)) return toast.error('Target potongan harus > 0.');
    setSaving(true);
    try {
      const created = await cuttingApi('POST', '/orders', token, {
        ...form,
        planned_input_qty: Number(form.planned_input_qty),
        planned_output_qty: Number(form.planned_output_qty),
      });
      toast.success(`Cutting ${created.number} dibuat (draft).`);
      setShowCreate(false);
      await load();
      openDetail(created.id);
    } catch (e2) {
      toast.error(e2.message);
    } finally {
      setSaving(false);
    }
  };

  const openDetail = async (id) => {
    setDetailLoading(true);
    setProg({ input_consumed: '', output_qty: '', waste_qty: '', note: '', roll_id: '', input_uom: '', roll_ids: [] });
    setDetailRolls({ items: [], roll_required: false, total_remaining: 0, uom: '' });
    try {
      const d = await cuttingApi('GET', `/orders/${id}`, token);
      setDetail(d);
      await loadDetailRolls(d);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDetailLoading(false);
    }
  };

  // FASE H-6: gulungan yang bisa dipotong untuk order ini. Dimuat setiap kali
  // detail dibuka/diperbarui supaya sisa tiap gulungan yang tampil = sisa nyata.
  const loadDetailRolls = useCallback(async (order) => {
    if (!order?.input_material_id) return;
    try {
      const res = await cuttingApi('GET', `/rolls?material_id=${order.input_material_id}`, token);
      const items = Array.isArray(res) ? res : (res?.items || []);
      setDetailRolls({
        items,
        roll_required: !!res?.roll_required,
        total_remaining: Number(res?.total_remaining || 0),
        uom: res?.uom || items[0]?.uom || '',
      });
    } catch {
      setDetailRolls({ items: [], roll_required: false, total_remaining: 0, uom: '' });
    }
  }, [token]);

  const refreshDetail = async (id) => {
    try {
      const d = await cuttingApi('GET', `/orders/${id}`, token);
      setDetail(d);
      await loadDetailRolls(d);
    } catch { /* ignore */ }
    load();
  };

  const doAction = async (path, body, okMsg) => {
    if (!detail) return;
    setActing(true);
    try {
      const res = await cuttingApi('POST', `/orders/${detail.id}${path}`, token, body);
      toast.success(okMsg);
      if (res?.notice) toast.info(res.notice, { duration: 6000 });
      await refreshDetail(detail.id);
    } catch (e) {
      toast.error(e.message, { duration: 8000 });
    } finally {
      setActing(false);
    }
  };

  // FASE H-6: rencana pemakaian gulungan (FIFO) dihitung di layar supaya operator
  // melihat "gulungan mana dipakai berapa" SEBELUM menekan Catat — cermin dari
  // `fabric_roll_engine.allocate()` di server.
  const pickedRolls = useMemo(
    () => detailRolls.items.filter((r) => (prog.roll_ids || []).includes(r.id)),
    [detailRolls.items, prog.roll_ids],
  );
  const consumedInOrderUnit = useMemo(() => {
    const q = Number(prog.input_consumed || 0);
    if (!q) return 0;
    // konversi satuan operator ditangani server; pratinjau memakai angka apa adanya
    return q;
  }, [prog.input_consumed]);
  const allocPreview = useMemo(
    () => previewAllocation(pickedRolls, consumedInOrderUnit),
    [pickedRolls, consumedInOrderUnit],
  );
  const rollBlocking = detailRolls.roll_required && (prog.roll_ids || []).length === 0;

  const toggleProgRoll = (id) => setProg((p) => {
    const has = (p.roll_ids || []).includes(id);
    return { ...p, roll_ids: has ? p.roll_ids.filter((x) => x !== id) : [...(p.roll_ids || []), id] };
  });

  const submitProgress = async (e) => {
    e.preventDefault();
    if (!(Number(prog.input_consumed) > 0)) return toast.error('Kain terpakai harus > 0.');
    if (!(Number(prog.output_qty) > 0)) return toast.error('Jumlah potongan jadi harus > 0.');
    if (rollBlocking) {
      return toast.error(
        'Pilih gulungan yang dipotong dulu — tanpa itu sisa gulungan di sistem akan menyimpang '
        + 'dari kenyataan dan lot kain tidak bisa dipertanggungjawabkan ke buyer.',
        { duration: 8000 });
    }
    setActing(true);
    try {
      const res = await cuttingApi('POST', `/orders/${detail.id}/progress`, token, {
        input_consumed: Number(prog.input_consumed),
        output_qty: Number(prog.output_qty),
        waste_qty: Number(prog.waste_qty || 0),
        note: prog.note,
        roll_ids: (prog.roll_ids || []).length ? prog.roll_ids : undefined,
        roll_id: prog.roll_id || undefined,
        input_uom: (effProgUom && effProgUom !== orderUnit) ? effProgUom : undefined,
      });
      toast.success('Progres tercatat — stok gudang sudah diperbarui.');
      const used = res?.last_progress?.roll_consumption || [];
      if (used.length) {
        toast.info(
          'Gulungan dipakai: ' + used.map((u) => `${u.roll_no} −${fmtQty(u.qty)} (sisa ${fmtQty(u.remaining_after)})`).join(' · '),
          { duration: 9000 });
      }
      setProg({ input_consumed: '', output_qty: '', waste_qty: '', note: '', roll_id: '', input_uom: '', roll_ids: [] });
      await refreshDetail(detail.id);
    } catch (e2) {
      toast.error(e2.message, { duration: 9000 });
    } finally {
      setActing(false);
    }
  };

  const removeDraft = async (row) => {
    if (!window.confirm(`Hapus draft ${row.number}?`)) return;
    try {
      await cuttingApi('DELETE', `/orders/${row.id}`, token);
      toast.success('Draft dihapus.');
      if (detail?.id === row.id) setDetail(null);
      load();
    } catch (e) {
      toast.error(e.message);
    }
  };

  return (
    <div className="space-y-5" data-testid="cutting-orders-module">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-orange-500/12 border border-orange-500/25 grid place-items-center">
            <Scissors className="w-5 h-5 text-orange-600 dark:text-orange-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground">Order Cutting</h2>
            <p className="text-sm text-muted-foreground">
              Ubah roll kain menjadi kain pola (potongan) — hasilnya jadi material untuk BOM produksi.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load}
            className="inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--card-surface)] text-sm text-foreground hover:bg-[var(--nav-pill-active)]"
            data-testid="cutting-refresh-btn">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Muat Ulang
          </button>
          <button onClick={openCreate}
            className="inline-flex items-center gap-2 h-9 px-4 rounded-lg bg-[hsl(var(--primary))] text-white text-sm font-medium hover:opacity-90"
            data-testid="cutting-create-btn">
            <Plus className="w-4 h-4" /> Buat Cutting
          </button>
        </div>
      </div>

      {/* Filters */}
      <GlassCard className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Cari nomor / style / kain / kode potongan…"
              className={`${inputCls} pl-9`}
              data-testid="cutting-search-input"
            />
          </div>
          <select value={status} onChange={(e) => setStatus(e.target.value)}
            className={`${inputCls} w-auto min-w-[160px]`} data-testid="cutting-status-filter">
            <option value="">Semua Status</option>
            <option value="draft">Draft</option>
            <option value="in_progress">Berjalan</option>
            <option value="completed">Selesai</option>
            <option value="cancelled">Dibatalkan</option>
          </select>
        </div>
      </GlassCard>

      {err && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-red-300 bg-red-50 dark:bg-red-500/10 dark:border-red-500/30 text-sm text-red-700 dark:text-red-300">
          <AlertCircle className="w-4 h-4" /> {err}
        </div>
      )}

      {/* Table */}
      <GlassCard className="p-0 overflow-hidden">
        {loading && rows.length === 0 ? (
          <div className="p-6 space-y-2">
            {[0, 1, 2, 3].map((i) => <div key={i} className="h-9 rounded-lg bg-foreground/5 animate-pulse" />)}
          </div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center" data-testid="cutting-empty-state">
            <Scissors className="w-10 h-10 mx-auto text-muted-foreground/40" />
            <p className="mt-3 font-medium text-foreground">Belum ada order cutting</p>
            <p className="text-sm text-muted-foreground">Mulai dengan memilih kain dari master material Gudang.</p>
            <button onClick={openCreate}
              className="mt-4 inline-flex items-center gap-2 h-9 px-4 rounded-lg bg-[hsl(var(--primary))] text-white text-sm">
              <Plus className="w-4 h-4" /> Buat Cutting
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="cutting-orders-table">
              <thead>
                <tr className="text-left text-xs text-muted-foreground border-b border-[var(--glass-border)] bg-[var(--nav-pill-bg)]">
                  <th className="px-4 py-2.5 font-medium">Nomor</th>
                  <th className="px-4 py-2.5 font-medium">Style / Potongan</th>
                  <th className="px-4 py-2.5 font-medium">Kain (input)</th>
                  <th className="px-4 py-2.5 font-medium text-right">Kain Terpakai</th>
                  <th className="px-4 py-2.5 font-medium text-right">Potongan Jadi</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium text-right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}
                    className="border-b border-[var(--glass-border)] last:border-0 hover:bg-[var(--nav-pill-active)]/40 cursor-pointer"
                    onClick={() => openDetail(r.id)}
                    data-testid={`cutting-row-${r.number}`}>
                    <td className="px-4 py-2.5 font-mono text-xs text-foreground whitespace-nowrap">{r.number}</td>
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-foreground">{r.style_name || '-'}</div>
                      <div className="text-[11px] text-muted-foreground font-mono">
                        {r.output_material_code || 'kode dibuat saat Mulai'}
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">
                      {r.input_material_name}<br />
                      <span className="font-mono">{r.input_material_code}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-foreground">
                      {fmtNum(r.consumed_input_qty, 2)} / {fmtNum(r.planned_input_qty, 2)} {r.input_unit}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      <span className="text-foreground font-medium">{fmtNum(r.produced_qty)}</span>
                      <span className="text-muted-foreground"> / {fmtNum(r.planned_output_qty)} pcs</span>
                      <div className="h-1 mt-1 rounded-full bg-foreground/10 overflow-hidden">
                        <div className="h-full bg-[hsl(var(--primary))]"
                             style={{ width: `${Math.min(r.progress_pct || 0, 100)}%` }} />
                      </div>
                    </td>
                    <td className="px-4 py-2.5"><StatusPill status={r.status} /></td>
                    <td className="px-4 py-2.5 text-right whitespace-nowrap">
                      <button onClick={(e) => { e.stopPropagation(); openDetail(r.id); }}
                        className="text-xs text-[hsl(var(--primary))] hover:underline mr-3">Detail</button>
                      {r.status === 'draft' && (
                        <button onClick={(e) => { e.stopPropagation(); removeDraft(r); }}
                          className="text-xs text-red-600 hover:underline inline-flex items-center gap-1">
                          <Trash2 className="w-3 h-3" /> Hapus
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>

      {/* ── CREATE MODAL ─────────────────────────────────────────────── */}
      {showCreate && (
        <Modal title="Buat Order Cutting" size="xl" onClose={() => setShowCreate(false)}>
          <form onSubmit={submitCreate} className="space-y-4" data-testid="cutting-create-form">
            <div className="rounded-lg border border-[var(--glass-border)] bg-[var(--nav-pill-bg)] p-3 text-xs text-muted-foreground flex items-start gap-2">
              <Layers className="w-4 h-4 mt-0.5 text-[hsl(var(--primary))] shrink-0" />
              <span>
                Input diambil dari <b className="text-foreground">master material Gudang</b> (kain / benang).
                Output otomatis dibuat sebagai <b className="text-foreground">item master baru</b> bertipe potongan
                (satuan pcs) saat cutting dimulai.
              </span>
            </div>

            <Field label="Material Kain (input)" required
                   hint={selectedMaterial
                     ? `Total stok ${fmtNum(selectedMaterial.stock_qty, 2)} ${selectedMaterial.unit} · ${selectedMaterial.roll_count} roll aktif`
                     : 'Stok kain disimpan per gudang — pilih kain dulu untuk melihat sebarannya.'}>
              <div className="flex items-center gap-2 mb-1.5">
                <label className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer">
                  <input type="checkbox" checked={onlyInStock}
                    onChange={(e) => setOnlyInStock(e.target.checked)}
                    data-testid="cutting-only-instock" />
                  Tampilkan hanya kain yang ada stoknya ({materialOptions.length} dari {materials.length})
                </label>
              </div>
              <select value={form.input_material_id} onChange={(e) => onPickMaterial(e.target.value)}
                className={inputCls} data-testid="cutting-input-material-select" required>
                <option value="">— Pilih kain —</option>
                {materialOptions.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.code} · {m.name} — stok {fmtNum(m.stock_qty, 2)} {m.unit}
                    {m.best_location_name ? ` @ ${m.best_location_name}` : ' (belum ada stok)'}
                  </option>
                ))}
              </select>
            </Field>

            {selectedMaterial && (
              <Field label="Gudang Sumber Kain" required
                     hint={stockAtLocation !== null
                       ? `Stok di gudang ini: ${fmtNum(stockAtLocation, 2)} ${selectedMaterial.unit}. Pemotongan stok saat input progres diambil dari gudang ini.`
                       : ''}>
                <select value={form.location_id}
                  onChange={(e) => setForm((f) => ({ ...f, location_id: e.target.value }))}
                  className={inputCls} data-testid="cutting-location-select" required>
                  <option value="">— Pilih gudang —</option>
                  {(selectedMaterial.stock_locations || []).map((l) => (
                    <option key={l.location_id} value={l.location_id}>
                      {l.location_name} — stok {fmtNum(l.qty, 2)} {selectedMaterial.unit}
                    </option>
                  ))}
                  {(selectedMaterial.stock_locations || []).length === 0 &&
                    locations.map((l) => (
                      <option key={l.id} value={l.id}>{l.name} (stok 0)</option>
                    ))}
                </select>
              </Field>
            )}

            {selectedMaterial && Number(selectedMaterial.stock_qty || 0) <= 0 && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30 text-xs text-amber-800 dark:text-amber-300">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                Kain ini belum punya stok di gudang manapun. Cutting bisa disimpan sebagai draft,
                tetapi tidak bisa dimulai sebelum penerimaan barang dicatat di Portal Gudang.
              </div>
            )}

            {/* ── FASE H-6: gulungan WAJIB untuk kain yang dilacak per gulungan ── */}
            {selectedMaterial && rollMeta.roll_required && rolls.length > 0 && (
              <Field label={`Gulungan Kain (${rolls.length} tersedia · sisa ${fmtQty(rollMeta.total_remaining)} ${rollMeta.uom})`}
                     hint="Centang gulungan yang akan dipotong. Boleh dipilih sekarang atau saat lapor progres — tetapi progres TIDAK bisa dicatat tanpa menunjuk gulungan.">
                <div className="max-h-40 overflow-y-auto rounded-lg border border-[var(--glass-border)] divide-y divide-[var(--glass-border)]"
                  data-testid="cutting-roll-picker">
                  {rolls.map((r) => {
                    const checked = form.roll_ids.includes(r.id);
                    const remaining = Number(r.remaining ?? (r.uom === 'kg' ? r.remaining_kg : r.remaining_m) ?? 0);
                    return (
                      <label key={r.id} className="flex items-center gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-[var(--nav-pill-active)]/40"
                        data-testid={`cutting-roll-option-${r.roll_no}`}>
                        <input type="checkbox" checked={checked}
                          onChange={() => setForm((f) => ({
                            ...f,
                            roll_ids: checked ? f.roll_ids.filter((x) => x !== r.id) : [...f.roll_ids, r.id],
                          }))} />
                        <span className="font-mono text-foreground">{r.roll_no}</span>
                        <span className="text-muted-foreground">
                          sisa {fmtQty(remaining)} {r.uom} · {r.color || r.color_lot || '-'}
                          {r.source_receipt_number ? ` · dari ${r.source_receipt_number}` : ''}
                        </span>
                      </label>
                    );
                  })}
                </div>
                {form.roll_ids.length > 0 && (
                  <p className="text-[11px] text-muted-foreground mt-1" data-testid="cutting-roll-picked-summary">
                    {form.roll_ids.length} gulungan dipilih · sisa terpilih{' '}
                    {fmtQty(rolls.filter((r) => form.roll_ids.includes(r.id))
                      .reduce((s, r) => s + Number(r.remaining ?? (r.uom === 'kg' ? r.remaining_kg : r.remaining_m) ?? 0), 0))} {rollMeta.uom}
                    {Number(form.planned_input_qty) > 0 && ` · rencana pakai ${fmtQty(form.planned_input_qty)} ${selectedMaterial.unit}`}
                  </p>
                )}
              </Field>
            )}

            {selectedMaterial && rollMeta.roll_required && rolls.length === 0 && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg border border-red-300 bg-red-50 dark:bg-red-500/10 dark:border-red-500/30 text-xs text-red-700 dark:text-red-300"
                data-testid="cutting-no-rolls-warning">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  Kain ini <b>belum punya gulungan</b> di sistem, jadi order tidak bisa disimpan — tidak akan
                  bisa dibuktikan gulungan mana yang dipotong. Terbitkan gulungannya dulu di
                  <b> Gudang → Roll Kain → tab “Penerimaan tanpa roll”</b>, atau isi Rincian Roll saat Penerimaan Barang.
                </span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label={`Rencana Pemakaian Kain (${selectedMaterial?.unit || 'satuan'})`} required>
                <input type="number" step="0.01" min="0" value={form.planned_input_qty}
                  onChange={(e) => setForm((f) => ({ ...f, planned_input_qty: e.target.value }))}
                  className={inputCls} data-testid="cutting-planned-input" required />
              </Field>
              <Field label="Target Potongan (pcs)" required>
                <input type="number" step="1" min="0" value={form.planned_output_qty}
                  onChange={(e) => setForm((f) => ({ ...f, planned_output_qty: e.target.value }))}
                  className={inputCls} data-testid="cutting-planned-output" required />
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Nama Style / Produk" required hint="Dipakai membentuk kode potongan.">
                <input value={form.style_name}
                  onChange={(e) => setForm((f) => ({ ...f, style_name: e.target.value }))}
                  placeholder="mis. Dress Jemina" className={inputCls}
                  data-testid="cutting-style-name" required />
              </Field>
              <Field label="SKU Style (opsional)">
                <input value={form.style_sku}
                  onChange={(e) => setForm((f) => ({ ...f, style_sku: e.target.value }))}
                  placeholder="mis. SP-JEMINA" className={inputCls} data-testid="cutting-style-sku" />
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Warna">
                <input value={form.output_color}
                  onChange={(e) => setForm((f) => ({ ...f, output_color: e.target.value }))}
                  placeholder={selectedMaterial?.color || 'mis. HITAM'} className={inputCls}
                  data-testid="cutting-output-color" />
              </Field>
              <Field label="Size">
                <input value={form.output_size}
                  onChange={(e) => setForm((f) => ({ ...f, output_size: e.target.value }))}
                  placeholder="mis. L" className={inputCls} data-testid="cutting-output-size" />
              </Field>
            </div>

            <Field label="Catatan">
              <textarea value={form.notes} rows={2}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                className={`${inputCls} h-auto py-2`} data-testid="cutting-notes" />
            </Field>

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowCreate(false)}
                className="h-9 px-4 rounded-lg border border-[var(--glass-border)] text-sm text-foreground">Batal</button>
              <button type="submit" disabled={saving}
                className="h-9 px-4 rounded-lg bg-[hsl(var(--primary))] text-white text-sm font-medium disabled:opacity-60 inline-flex items-center gap-2"
                data-testid="cutting-submit-create">
                {saving && <Loader2 className="w-4 h-4 animate-spin" />} Simpan Draft
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── DETAIL MODAL ─────────────────────────────────────────────── */}
      {detail && (
        <Modal title={`Cutting ${detail.number}`} size="2xl" onClose={() => setDetail(null)}>
          <div className="space-y-4" data-testid="cutting-detail-panel">
            {detailLoading && <div className="h-1 bg-[hsl(var(--primary))] animate-pulse rounded" />}

            {/* Ringkas */}
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={detail.status} />
              <span className="text-xs text-muted-foreground">Dibuat {fmtDateTime(detail.created_at)} oleh {detail.created_by_name || '-'}</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <GlassCard className="p-3">
                <p className="text-[11px] text-muted-foreground">Kain (input)</p>
                <p className="text-sm font-medium text-foreground mt-0.5">{detail.input_material_name}</p>
                <p className="text-[11px] font-mono text-muted-foreground">{detail.input_material_code}</p>
                <p className="text-xs mt-2 text-foreground">
                  Terpakai <b>{fmtNum(detail.consumed_input_qty, 2)}</b> / {fmtNum(detail.planned_input_qty, 2)} {detail.input_unit}
                </p>
                <p className="text-[11px] text-muted-foreground">Stok gudang saat ini: {fmtNum(detail.input_stock, 2)} {detail.input_unit}</p>
                <p className="text-[11px] text-muted-foreground">Gudang sumber: <b className="text-foreground">{detail.location_name || '-'}</b></p>
                {detailRolls.roll_required && (
                  <p className="text-[11px] mt-1.5 text-violet-700 dark:text-violet-300" data-testid="cutting-roll-summary">
                    {detailRolls.items.length} gulungan bersisa · total {fmtQty(detailRolls.total_remaining)} {detailRolls.uom}
                  </p>
                )}
                {(detail.roll_ids || []).some((r) => Number(r.consumed_qty || 0) > 0) && (
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Sudah dipakai:{' '}
                    {(detail.roll_ids || []).filter((r) => Number(r.consumed_qty || 0) > 0)
                      .map((r) => `${r.roll_no} (${fmtQty(r.consumed_qty)})`).join(', ')}
                  </p>
                )}
              </GlassCard>
              <div className="hidden md:flex items-center justify-center">
                <ArrowRight className="w-5 h-5 text-muted-foreground" />
              </div>
              <GlassCard className="p-3">
                <p className="text-[11px] text-muted-foreground">Potongan (output)</p>
                <p className="text-sm font-medium text-foreground mt-0.5">
                  {detail.output_material_name || `${detail.style_name} ${detail.output_color} ${detail.output_size}`}
                </p>
                <p className="text-[11px] font-mono text-muted-foreground">
                  {detail.output_material_code || 'kode dibuat saat Mulai'}
                </p>
                <p className="text-xs mt-2 text-foreground">
                  Jadi <b>{fmtNum(detail.produced_qty)}</b> / {fmtNum(detail.planned_output_qty)} pcs
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Stok potongan: {fmtNum(detail.output_stock)} pcs
                  {detail.output_unit_cost > 0 && ` · HPP ${fmtRp(detail.output_unit_cost)}/pcs`}
                </p>
              </GlassCard>
            </div>

            {/* Aksi status */}
            <div className="flex flex-wrap gap-2">
              {detail.status === 'draft' && (
                <button onClick={() => doAction('/start', {}, 'Cutting dimulai — master potongan dibuat.')}
                  disabled={acting}
                  className="inline-flex items-center gap-2 h-9 px-4 rounded-lg bg-[hsl(var(--primary))] text-white text-sm disabled:opacity-60"
                  data-testid="cutting-start-btn">
                  <PlayCircle className="w-4 h-4" /> Mulai Cutting
                </button>
              )}
              {detail.status === 'in_progress' && (
                <button onClick={() => doAction('/complete', {}, 'Cutting selesai — HPP potongan dihitung.')}
                  disabled={acting}
                  className="inline-flex items-center gap-2 h-9 px-4 rounded-lg bg-emerald-600 text-white text-sm disabled:opacity-60"
                  data-testid="cutting-complete-btn">
                  <CheckCircle2 className="w-4 h-4" /> Selesaikan
                </button>
              )}
              {(detail.status === 'draft' || detail.status === 'in_progress') && (
                <button onClick={() => doAction('/cancel', { reason: 'dibatalkan user' }, 'Cutting dibatalkan.')}
                  disabled={acting}
                  className="inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-red-300 dark:border-red-500/30 text-red-600 dark:text-red-400 text-sm disabled:opacity-60"
                  data-testid="cutting-cancel-btn">
                  <XCircle className="w-4 h-4" /> Batalkan
                </button>
              )}
              {detail.status === 'completed' && detail.output_material_code && (
                <button onClick={() => onNavigate?.('cutting-panels')}
                  className="inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-[var(--glass-border)] text-sm text-foreground"
                  data-testid="cutting-goto-panels">
                  <Package className="w-4 h-4" /> Lihat Master Potongan
                </button>
              )}
            </div>

            {/* Input progres */}
            {detail.status === 'in_progress' && (
              <GlassCard className="p-4">
                <h4 className="text-sm font-semibold text-foreground mb-1">Input Progres Potong</h4>
                <p className="text-xs text-muted-foreground mb-3">
                  Setiap input langsung memotong stok kain, menambah stok potongan, dan mengurangi sisa
                  gulungan yang ditunjuk{detailRolls.roll_required
                    ? ' — untuk kain yang dilacak per gulungan, gulungan WAJIB dipilih.'
                    : '.'}
                </p>
                <form onSubmit={submitProgress} className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end"
                      data-testid="cutting-progress-form">
                  <Field label={`Kain Terpakai (${effProgUom || detail.input_unit})`} required>
                    <div className="flex gap-2">
                      <input type="number" step="0.0001" min="0" value={prog.input_consumed}
                        onChange={(e) => setProg((p) => ({ ...p, input_consumed: e.target.value }))}
                        className={inputCls} data-testid="cutting-progress-input" required />
                      <UomSelect opt={progUomOpt} value={effProgUom} fallbackUnit={detail.input_unit}
                        onChange={(e) => setProg((p) => ({ ...p, input_uom: e.target.value }))}
                        testId="cutting-progress-uom" className="w-20 shrink-0" />
                    </div>
                    <UomConversionHint opt={progUomOpt} qty={prog.input_consumed} unit={effProgUom}
                      fallbackUnit={detail.input_unit} className="mt-1" testId="cutting-progress-uom-hint" />
                  </Field>
                  <Field label="Potongan Jadi (pcs)" required>
                    <input type="number" step="1" min="0" value={prog.output_qty}
                      onChange={(e) => setProg((p) => ({ ...p, output_qty: e.target.value }))}
                      className={inputCls} data-testid="cutting-progress-output" required />
                  </Field>
                  <Field label="Waste / Sisa">
                    <input type="number" step="0.01" min="0" value={prog.waste_qty}
                      onChange={(e) => setProg((p) => ({ ...p, waste_qty: e.target.value }))}
                      className={inputCls} data-testid="cutting-progress-waste" />
                  </Field>
                  <button type="submit" disabled={acting || rollBlocking || allocPreview.shortage > 0}
                    className="h-9 px-4 rounded-lg bg-[hsl(var(--primary))] text-white text-sm font-medium disabled:opacity-60 inline-flex items-center justify-center gap-2"
                    data-testid="cutting-progress-submit">
                    {acting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Catat
                  </button>
                  {(detailRolls.roll_required || (detail.roll_ids || []).length > 0) && (
                    <div className="sm:col-span-4">
                      <Field
                        label={detailRolls.roll_required ? 'Gulungan yang dipotong (WAJIB)' : 'Gulungan yang dipotong'}
                        required={detailRolls.roll_required}
                        hint={detailRolls.items.length
                          ? 'Centang gulungan yang benar-benar dipotong. Pemakaian dibagi otomatis FIFO (gulungan tertua dulu) dan sisanya langsung berkurang.'
                          : ''}>
                        {detailRolls.items.length === 0 ? (
                          <div className="flex items-start gap-2 p-2.5 rounded-lg border border-red-300 bg-red-50 dark:bg-red-500/10 dark:border-red-500/30 text-xs text-red-700 dark:text-red-300"
                            data-testid="cutting-progress-no-rolls">
                            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                            <span>
                              Kain ini tidak punya gulungan bersisa. Terbitkan gulungan di{' '}
                              <b>Gudang → Roll Kain → “Penerimaan tanpa roll”</b>
                              {onNavigate && (
                                <button type="button" onClick={() => onNavigate('wms-fabric-rolls')}
                                  className="ml-1 underline font-medium" data-testid="cutting-goto-rolls">
                                  buka sekarang →
                                </button>
                              )}
                            </span>
                          </div>
                        ) : (
                          <>
                            <div className="max-h-40 overflow-y-auto rounded-lg border border-[var(--glass-border)] divide-y divide-[var(--glass-border)]"
                              data-testid="cutting-progress-roll-picker">
                              {detailRolls.items.map((r) => {
                                const checked = (prog.roll_ids || []).includes(r.id);
                                const remaining = Number(r.remaining ?? (r.uom === 'kg' ? r.remaining_kg : r.remaining_m) ?? 0);
                                const inPlan = allocPreview.plan.find((p) => p.roll_id === r.id);
                                return (
                                  <label key={r.id}
                                    className={`flex items-center gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-[var(--nav-pill-active)]/40 ${checked ? 'bg-[var(--nav-pill-active)]/30' : ''}`}
                                    data-testid={`cutting-progress-roll-${r.roll_no}`}>
                                    <input type="checkbox" checked={checked}
                                      onChange={() => toggleProgRoll(r.id)}
                                      data-testid={`cutting-progress-roll-cb-${r.roll_no}`} />
                                    <span className="font-mono text-foreground">{r.roll_no}</span>
                                    <span className="text-muted-foreground">
                                      sisa {fmtQty(remaining)} {r.uom}
                                      {r.color_lot ? ` · lot ${r.color_lot}` : ''}
                                      {r.source_receipt_number ? ` · dari ${r.source_receipt_number}` : ''}
                                    </span>
                                    {inPlan && (
                                      <span className="ml-auto text-[11px] font-semibold text-[hsl(var(--primary))]">
                                        pakai {fmtQty(inPlan.qty)} → sisa {fmtQty(inPlan.remaining_after)}
                                      </span>
                                    )}
                                  </label>
                                );
                              })}
                            </div>
                            {/* Pratinjau alokasi FIFO — supaya tidak ada kejutan setelah ditekan */}
                            {(prog.roll_ids || []).length > 0 && Number(prog.input_consumed) > 0 && (
                              <div className={`mt-1.5 text-[11px] px-2.5 py-1.5 rounded-lg border ${
                                allocPreview.shortage > 0
                                  ? 'border-red-300 bg-red-50 dark:bg-red-500/10 dark:border-red-500/30 text-red-700 dark:text-red-300'
                                  : 'border-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 dark:border-emerald-500/30 text-emerald-700 dark:text-emerald-300'}`}
                                data-testid="cutting-alloc-preview">
                                {allocPreview.shortage > 0 ? (
                                  <>Sisa gulungan terpilih kurang {fmtQty(allocPreview.shortage, 3)} {detailRolls.uom} —
                                     tersedia {fmtQty(allocPreview.available)} untuk {fmtQty(prog.input_consumed)}.
                                     Pilih gulungan tambahan atau kurangi jumlah pemakaian.</>
                                ) : (
                                  <>Rencana: {allocPreview.plan.map((p) => `${p.roll_no} −${fmtQty(p.qty)}`).join(' · ')}</>
                                )}
                              </div>
                            )}
                            {rollBlocking && (
                              <p className="mt-1.5 text-[11px] text-amber-700 dark:text-amber-300" data-testid="cutting-roll-required-hint">
                                Pilih minimal satu gulungan — progres tidak bisa dicatat tanpa itu.
                              </p>
                            )}
                          </>
                        )}
                      </Field>
                    </div>
                  )}
                  <div className="sm:col-span-2">
                    <Field label="Catatan">
                      <input value={prog.note} onChange={(e) => setProg((p) => ({ ...p, note: e.target.value }))}
                        placeholder="mis. shift pagi" className={inputCls} data-testid="cutting-progress-note" />
                    </Field>
                  </div>
                </form>
              </GlassCard>
            )}

            {/* Riwayat progres */}
            <GlassCard className="p-0 overflow-hidden">
              <div className="px-4 py-2.5 border-b border-[var(--glass-border)] flex items-center gap-2">
                <History className="w-4 h-4 text-muted-foreground" />
                <h4 className="text-sm font-semibold text-foreground">Riwayat Progres ({(detail.progress || []).length})</h4>
              </div>
              {(detail.progress || []).length === 0 ? (
                <p className="p-6 text-center text-sm text-muted-foreground">Belum ada progres dicatat.</p>
              ) : (
                <table className="w-full text-sm" data-testid="cutting-progress-table">
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground border-b border-[var(--glass-border)]">
                      <th className="px-4 py-2 font-medium">Waktu</th>
                      <th className="px-4 py-2 font-medium text-right">Kain</th>
                      <th className="px-4 py-2 font-medium text-right">Potongan</th>
                      <th className="px-4 py-2 font-medium text-right">Waste</th>
                      <th className="px-4 py-2 font-medium">Gulungan dipakai</th>
                      <th className="px-4 py-2 font-medium">Catatan</th>
                      <th className="px-4 py-2 font-medium">Oleh</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.progress || []).map((p) => (
                      <tr key={p.id} className="border-b border-[var(--glass-border)] last:border-0">
                        <td className="px-4 py-2 text-xs text-muted-foreground">{fmtDateTime(p.created_at)}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-foreground">{fmtNum(p.input_consumed, 2)}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-foreground">{fmtNum(p.output_qty)}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">{fmtNum(p.waste_qty, 2)}</td>
                        <td className="px-4 py-2 text-xs" data-testid={`cutting-progress-rolls-${p.id}`}>
                          {(p.roll_consumption || []).length ? (
                            <div className="flex flex-wrap gap-1">
                              {p.roll_consumption.map((rc) => (
                                <span key={rc.roll_id}
                                  className="font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-violet-100 dark:bg-violet-400/15 text-violet-800 dark:text-violet-200 border border-violet-300 dark:border-violet-400/30"
                                  title={`sisa setelah dipakai: ${fmtQty(rc.remaining_after)}`}>
                                  {rc.roll_no} −{fmtQty(rc.qty)}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">{p.roll_id ? 'tercatat' : '—'}</span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-xs text-muted-foreground">{p.note || '-'}</td>
                        <td className="px-4 py-2 text-xs text-muted-foreground">{p.created_by_name || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </GlassCard>

            {detail.notes && (
              <p className="text-xs text-muted-foreground">Catatan: {detail.notes}</p>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
