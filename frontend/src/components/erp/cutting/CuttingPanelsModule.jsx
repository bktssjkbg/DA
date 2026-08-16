/**
 * CuttingPanelsModule — Master Potongan (kain pola) hasil cutting.
 *
 * Ini BUKAN master material baru yang terpisah: isinya adalah dokumen
 * `rahaza_materials` bertanda `is_cut_panel`, jadi item yang tampil di sini
 * juga tampil di Master Item Gudang, dropdown BOM, dan Pengeluaran Material.
 * Layar ini hanya menyaringnya supaya tim cutting/gudang mudah melihat
 * stok potongan per style/warna/size beserta kain asalnya.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Package, RefreshCw, Search, Scissors, ArrowRight, AlertCircle } from 'lucide-react';
import { GlassCard } from '@/components/ui/glass';
import { cuttingApi, fmtNum, fmtRp, fmtDate } from './cuttingApi';

export default function CuttingPanelsModule({ token, onNavigate }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setErr('');
    try {
      setRows(await cuttingApi('GET', '/output-materials', token));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) =>
      [r.code, r.name, r.color, r.style_name, r.style_sku, r.source_material_code]
        .filter(Boolean).some((v) => String(v).toLowerCase().includes(s)));
  }, [rows, q]);

  const totalStock = filtered.reduce((a, r) => a + Number(r.stock_qty || 0), 0);
  const totalValue = filtered.reduce((a, r) => a + Number(r.stock_qty || 0) * Number(r.unit_cost || 0), 0);

  return (
    <div className="space-y-5" data-testid="cutting-panels-module">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-emerald-500/12 border border-emerald-500/25 grid place-items-center">
            <Package className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-foreground">Master Potongan</h2>
            <p className="text-sm text-muted-foreground">
              Item material hasil cutting (kain pola). Siap dipakai sebagai BOM produksi & dikirim ke CMT.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load}
            className="inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-[var(--glass-border)] bg-[var(--card-surface)] text-sm text-foreground hover:bg-[var(--nav-pill-active)]"
            data-testid="cutting-panels-refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Muat Ulang
          </button>
          <button onClick={() => onNavigate?.('cutting-orders')}
            className="inline-flex items-center gap-2 h-9 px-4 rounded-lg bg-[hsl(var(--primary))] text-white text-sm"
            data-testid="cutting-panels-goto-orders">
            <Scissors className="w-4 h-4" /> Order Cutting
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <GlassCard className="p-4">
          <p className="text-xs text-muted-foreground">Jenis Potongan</p>
          <p className="text-2xl font-bold text-foreground mt-1">{fmtNum(filtered.length)}</p>
        </GlassCard>
        <GlassCard className="p-4">
          <p className="text-xs text-muted-foreground">Total Stok Potongan</p>
          <p className="text-2xl font-bold text-foreground mt-1">{fmtNum(totalStock)} pcs</p>
        </GlassCard>
        <GlassCard className="p-4">
          <p className="text-xs text-muted-foreground">Nilai Persediaan</p>
          <p className="text-2xl font-bold text-foreground mt-1">{fmtRp(totalValue)}</p>
        </GlassCard>
      </div>

      <GlassCard className="p-3">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Cari kode / style / warna / kain asal…"
            className="w-full h-9 pl-9 pr-3 rounded-lg border border-[var(--glass-border)] bg-[var(--input-surface)] text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary)/0.35)]"
            data-testid="cutting-panels-search" />
        </div>
      </GlassCard>

      {err && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-red-300 bg-red-50 dark:bg-red-500/10 dark:border-red-500/30 text-sm text-red-700 dark:text-red-300">
          <AlertCircle className="w-4 h-4" /> {err}
        </div>
      )}

      <GlassCard className="p-0 overflow-hidden">
        {loading && rows.length === 0 ? (
          <div className="p-6 space-y-2">
            {[0, 1, 2].map((i) => <div key={i} className="h-9 rounded-lg bg-foreground/5 animate-pulse" />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center" data-testid="cutting-panels-empty">
            <Package className="w-10 h-10 mx-auto text-muted-foreground/40" />
            <p className="mt-3 font-medium text-foreground">Belum ada master potongan</p>
            <p className="text-sm text-muted-foreground">
              Item potongan otomatis dibuat saat sebuah order cutting dimulai.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="cutting-panels-table">
              <thead>
                <tr className="text-left text-xs text-muted-foreground border-b border-[var(--glass-border)] bg-[var(--nav-pill-bg)]">
                  <th className="px-4 py-2.5 font-medium">Kode Potongan</th>
                  <th className="px-4 py-2.5 font-medium">Nama</th>
                  <th className="px-4 py-2.5 font-medium">Warna / Size</th>
                  <th className="px-4 py-2.5 font-medium">Kain Asal</th>
                  <th className="px-4 py-2.5 font-medium text-right">Stok</th>
                  <th className="px-4 py-2.5 font-medium text-right">HPP / pcs</th>
                  <th className="px-4 py-2.5 font-medium">Dibuat</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((m) => (
                  <tr key={m.id} className="border-b border-[var(--glass-border)] last:border-0 hover:bg-[var(--nav-pill-active)]/40">
                    <td className="px-4 py-2.5 font-mono text-xs text-foreground">{m.code}</td>
                    <td className="px-4 py-2.5 text-foreground">{m.name}</td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">
                      {m.color || '-'}{m.size ? ` · ${m.size}` : ''}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      <span className="inline-flex items-center gap-1 text-muted-foreground">
                        <span className="font-mono">{m.source_material_code || '-'}</span>
                        <ArrowRight className="w-3 h-3" />
                        <span className="font-mono text-foreground">{m.code}</span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-medium text-foreground">
                      {fmtNum(m.stock_qty)} pcs
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-muted-foreground">
                      {m.unit_cost ? fmtRp(m.unit_cost) : '-'}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">{fmtDate(m.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
