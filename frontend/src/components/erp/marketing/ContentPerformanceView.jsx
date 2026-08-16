/**
 * ContentPerformanceView — PERFORMA KONTEN & KREATOR (F7.3/F7.4).
 *
 * Kenapa layar ini ada: kalender konten menjawab "apa yang akan diposting", bukan
 * "konten mana yang menghasilkan". Tanpa layar ini, KPI konten yang sudah diisi tidak
 * pernah bisa dibaca per kreator untuk rapat mingguan.
 *
 * Dua angka omzet DIPISAH dengan sengaja: `GMV (KPI)` dari platform per konten, dan
 * `Omzet pesanan` dari pesanan nyata (`marketing_orders.creator_id`). Menjumlahkannya
 * berarti menghitung satu penjualan dua kali — jadi layar menaruhnya bersebelahan
 * beserta **cakupan KPI** supaya pembaca tahu berapa bagian yang benar-benar terukur.
 */
import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Loader2, Table2, LayoutGrid, Info, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GlassCard } from '@/components/ui/glass';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { formatRupiah } from '@/lib/format';

const API = process.env.REACT_APP_BACKEND_URL;
const fmtRp = formatRupiah;
const fmtNum = (n) => new Intl.NumberFormat('id-ID').format(Math.round(n || 0));
const VIEW_KEY = 'content_perf_view';
const GROUPS = [
  { v: 'creator', l: 'Per Kreator' },
  { v: 'content_type', l: 'Per Jenis Konten' },
  { v: 'account', l: 'Per Toko' },
];
const HEADS = ['Nama', 'Konten', 'Terbit', 'KPI terisi', 'Cakupan KPI', 'Views',
  'Views/konten', 'Engagement', 'Eng. rate', 'Saves', 'CTR rata2', 'Order (KPI)',
  'GMV (KPI)', 'GMV/konten', 'Omzet pesanan', 'Pesanan'];

export default function ContentPerformanceView({ token }) {
  const today = new Date();
  const first = new Date(today.getFullYear(), today.getMonth(), 1);
  const [from, setFrom] = useState(first.toISOString().slice(0, 10));
  const [to, setTo] = useState(today.toISOString().slice(0, 10));
  const [groupBy, setGroupBy] = useState('creator');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState(() => {
    try { return localStorage.getItem(VIEW_KEY) || 'table'; } catch { return 'table'; }
  });

  useEffect(() => { try { localStorage.setItem(VIEW_KEY, view); } catch { /* diblokir */ } }, [view]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/marketing/content-calendar/performance`
        + `?group_by=${groupBy}&date_from=${from}&date_to=${to}`,
        { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      toast.error(`Gagal memuat performa konten: ${e.message}`);
      setData(null);
    } finally { setLoading(false); }
  }, [groupBy, from, to, token]);

  useEffect(() => { load(); }, [load]);

  const t = data?.totals || {};
  const rows = data?.rows || [];

  return (
    <div className="space-y-4" data-testid="content-performance-view">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="text-[11px] text-muted-foreground block">Dari</label>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            data-testid="perf-date-from"
            className="h-8 rounded-md border border-border bg-background text-foreground px-2 text-xs" />
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground block">Sampai</label>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            data-testid="perf-date-to"
            className="h-8 rounded-md border border-border bg-background text-foreground px-2 text-xs" />
        </div>
        <div>
          <label className="text-[11px] text-muted-foreground block">Kelompokkan</label>
          <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}
            data-testid="perf-group-by"
            className="h-8 rounded-md border border-border bg-background text-foreground px-2 text-xs">
            {GROUPS.map((g) => <option key={g.v} value={g.v}>{g.l}</option>)}
          </select>
        </div>
        <div className="flex rounded-md border border-border overflow-hidden ml-auto">
          <button type="button" onClick={() => setView('table')} data-testid="perf-view-table"
            className={`px-2 py-1.5 text-xs flex items-center gap-1 ${view === 'table'
              ? 'bg-primary text-primary-foreground' : 'bg-background text-foreground'}`}>
            <Table2 size={12} /> Tabel
          </button>
          <button type="button" onClick={() => setView('grid')} data-testid="perf-view-grid"
            className={`px-2 py-1.5 text-xs flex items-center gap-1 ${view === 'grid'
              ? 'bg-primary text-primary-foreground' : 'bg-background text-foreground'}`}>
            <LayoutGrid size={12} /> Kartu
          </button>
        </div>
        <Button size="sm" variant="outline" className="h-8" onClick={load} disabled={loading}
          data-testid="perf-refresh">
          <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3" data-testid="perf-kpi">
        <GlassCard className="p-3"><p className="text-[11px] text-muted-foreground">Konten</p>
          <p className="text-base font-bold">{fmtNum(t.contents)}</p>
          <p className="text-[10px] text-muted-foreground">{fmtNum(t.posted)} terbit</p></GlassCard>
        <GlassCard className="p-3"><p className="text-[11px] text-muted-foreground">Cakupan KPI</p>
          <p className="text-base font-bold">{Number(t.kpi_coverage_pct || 0).toFixed(1)}%</p>
          <p className="text-[10px] text-muted-foreground">{fmtNum(t.with_kpi)} konten ber-KPI</p></GlassCard>
        <GlassCard className="p-3"><p className="text-[11px] text-muted-foreground">Views</p>
          <p className="text-base font-bold">{fmtNum(t.views)}</p></GlassCard>
        <GlassCard className="p-3"><p className="text-[11px] text-muted-foreground">Engagement</p>
          <p className="text-base font-bold">{fmtNum(t.engagement)}</p></GlassCard>
        <GlassCard className="p-3"><p className="text-[11px] text-muted-foreground">GMV (KPI platform)</p>
          <p className="text-base font-bold">{fmtRp(t.gmv_kpi)}</p></GlassCard>
        <GlassCard className="p-3"><p className="text-[11px] text-muted-foreground">Omzet pesanan</p>
          <p className="text-base font-bold">{fmtRp(t.order_revenue)}</p>
          <p className="text-[10px] text-muted-foreground">dari pesanan ber-kreator</p></GlassCard>
      </div>

      {loading ? (
        <div className="py-10 text-center text-muted-foreground text-sm">
          <Loader2 className="mx-auto animate-spin mb-2" size={18} /> Menghitung performa konten…
        </div>
      ) : !rows.length ? (
        <div className="py-10 text-center text-muted-foreground text-sm" data-testid="perf-empty">
          Belum ada konten pada rentang tanggal ini.
        </div>
      ) : view === 'table' ? (
        <div className="rounded-lg border border-border overflow-x-auto bg-background">
          <table className="w-full text-xs" data-testid="perf-table">
            <thead className="bg-muted/60"><tr>{HEADS.map((h) => (
              <th key={h} className="px-2.5 py-2 text-left font-semibold whitespace-nowrap">{h}</th>
            ))}</tr></thead>
            <tbody className="divide-y">
              {rows.map((r) => (
                <tr key={r.key} className="hover:bg-muted/30" data-testid={`perf-row-${r.key}`}>
                  <td className="px-2.5 py-2">
                    <div className="font-semibold text-foreground">{r.label}</div>
                    {r.creator_code ? <div className="text-[10px] text-muted-foreground">{r.creator_code}</div> : null}
                  </td>
                  <td className="px-2.5 py-2">{fmtNum(r.contents)}</td>
                  <td className="px-2.5 py-2">{fmtNum(r.posted)}</td>
                  <td className="px-2.5 py-2">{fmtNum(r.with_kpi)}</td>
                  <td className="px-2.5 py-2">
                    <span className={r.kpi_coverage_pct >= 80 ? 'text-emerald-600' : 'text-amber-600'}>
                      {Number(r.kpi_coverage_pct || 0).toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-2.5 py-2">{fmtNum(r.views)}</td>
                  <td className="px-2.5 py-2">{fmtNum(r.views_per_content)}</td>
                  <td className="px-2.5 py-2">{fmtNum(r.engagement)}</td>
                  <td className="px-2.5 py-2">{Number(r.engagement_rate || 0).toFixed(2)}%</td>
                  <td className="px-2.5 py-2">{fmtNum(r.saves)}</td>
                  <td className="px-2.5 py-2">{Number(r.ctr_avg || 0).toFixed(2)}%</td>
                  <td className="px-2.5 py-2">{fmtNum(r.orders)}</td>
                  <td className="px-2.5 py-2 font-semibold whitespace-nowrap">{fmtRp(r.gmv_kpi)}</td>
                  <td className="px-2.5 py-2 whitespace-nowrap">{fmtRp(r.gmv_per_content)}</td>
                  <td className="px-2.5 py-2 whitespace-nowrap">{fmtRp(r.order_revenue)}</td>
                  <td className="px-2.5 py-2">{fmtNum(r.order_count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" data-testid="perf-grid">
          {rows.map((r) => (
            <Card key={r.key} data-testid={`perf-card-${r.key}`}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-sm flex items-center gap-1.5">
                    <Users size={13} className="text-violet-500" /> {r.label}
                  </CardTitle>
                  <Badge variant="outline" className="text-[9px]">
                    KPI {Number(r.kpi_coverage_pct || 0).toFixed(0)}%
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-1 text-[11px]">
                <div className="flex justify-between"><span className="text-muted-foreground">Konten / terbit</span>
                  <span>{fmtNum(r.contents)} / {fmtNum(r.posted)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Views</span>
                  <span>{fmtNum(r.views)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Engagement</span>
                  <span>{fmtNum(r.engagement)} · {Number(r.engagement_rate || 0).toFixed(2)}%</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">GMV (KPI)</span>
                  <span className="font-semibold">{fmtRp(r.gmv_kpi)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Omzet pesanan</span>
                  <span>{fmtRp(r.order_revenue)}</span></div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {(data?.data_notes || []).length > 0 && (
        <div className="rounded-lg border border-border bg-muted/40 p-3" data-testid="perf-notes">
          <p className="text-xs font-semibold mb-1 flex items-center gap-1 text-foreground">
            <Info size={12} /> Catatan kejujuran data
          </p>
          <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-muted-foreground">
            {(data.data_notes || []).map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
