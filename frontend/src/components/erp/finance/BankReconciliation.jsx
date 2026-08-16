import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import PaginationBar from '@/components/ui/PaginationBar';
import {
  Loader2, Plus, Check, X, Link, LinkIcon, Unlink, CheckCircle2,
  AlertCircle, FileText, Upload, ArrowLeftRight, TrendingUp, RotateCcw
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { formatRupiah } from '@/lib/format';

const API = process.env.REACT_APP_BACKEND_URL;

const fmt = formatRupiah;

const STATUS_CFG = {
  draft:       { label: 'Draft',       color: 'bg-muted text-foreground border-border' },
  in_progress: { label: 'Diproses',    color: 'bg-blue-100 text-blue-700 border-blue-200' },
  approved:    { label: 'Disetujui',   color: 'bg-green-100 text-green-700 border-green-200' },
};

// ── Dashboard / Sessions list ────────────────────────────────────────────────
function SessionList({ headers, onOpen }) {
  const { toast } = useToast();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const LIMIT = 15;
  const [form, setForm] = useState({
    period: new Date().toISOString().slice(0, 7),
    bank_name: '', account_no: '', account_name: '',
    opening_balance: 0, closing_balance: 0, notes: '',
  });

  const load = useCallback(async () => {
    try {
      const [sRes, sumRes] = await Promise.all([
        axios.get(`${API}/api/finance/bank-recon/sessions`, { headers, params: { skip, limit: LIMIT } }),
        axios.get(`${API}/api/finance/bank-recon/summary`, { headers }),
      ]);
      setItems(sRes.data.items || []);
      setTotal(sRes.data.total || 0);
      setSummary(sumRes.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [headers, skip]);

  useEffect(() => { load(); }, [load]);

  const createSession = async () => {
    if (!form.bank_name || !form.period) { toast({ title: 'Isi nama bank dan periode.', variant: 'destructive' }); return; }
    try {
      const { data } = await axios.post(`${API}/api/finance/bank-recon/sessions`, form, { headers });
      toast({ title: 'Sesi rekonsiliasi berhasil dibuat.' });
      setShowCreate(false);
      load();
      onOpen(data);
    } catch (e) {
      toast({ title: e.response?.data?.detail || 'Gagal.', variant: 'destructive' });
    }
  };

  const deleteSession = async (id) => {
    if (!window.confirm('Hapus sesi ini?')) return;
    try {
      await axios.delete(`${API}/api/finance/bank-recon/sessions/${id}`, { headers });
      toast({ title: 'Sesi dihapus.' });
      load();
    } catch (e) {
      toast({ title: e.response?.data?.detail || 'Gagal.', variant: 'destructive' });
    }
  };

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Total Sesi', val: summary.total_sessions, color: 'blue' },
            { label: 'Draft', val: summary.draft, color: 'gray' },
            { label: 'Diproses', val: summary.in_progress, color: 'amber' },
            { label: 'Disetujui', val: summary.approved, color: 'green' },
          ].map((c, i) => (
            <Card key={i} className="hover:shadow-sm transition-shadow">
              <CardContent className="pt-4 pb-3">
                <p className="text-2xl font-bold">{c.val}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{c.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {summary?.total_unmatched > 0 && (
        <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 text-sm">
          <AlertCircle className="w-4 h-4 text-amber-600" />
          <span className="text-amber-800">Ada <strong>{summary.total_unmatched}</strong> transaksi yang belum dicocokkan di semua sesi aktif.</span>
        </div>
      )}

      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Daftar Sesi Rekonsiliasi</h3>
        <Button data-testid="btn-create-session" size="sm" onClick={() => setShowCreate(v => !v)}>
          <Plus className="w-4 h-4 mr-1" /> Sesi Baru
        </Button>
      </div>

      {showCreate && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader className="pb-2"><CardTitle className="text-sm">Buat Sesi Rekonsiliasi</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium mb-1 block">Periode * (YYYY-MM)</label>
                <input type="month" data-testid="input-period"
                  className="w-full border rounded-lg px-3 py-2 text-sm outline-none"
                  value={form.period} onChange={e => setForm(f => ({ ...f, period: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Nama Bank *</label>
                <input data-testid="input-bank-name"
                  className="w-full border rounded-lg px-3 py-2 text-sm outline-none"
                  value={form.bank_name} onChange={e => setForm(f => ({ ...f, bank_name: e.target.value }))}
                  placeholder="BCA, Mandiri, BRI..." />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">No. Rekening</label>
                <input data-testid="input-account-no"
                  className="w-full border rounded-lg px-3 py-2 text-sm outline-none"
                  value={form.account_no} onChange={e => setForm(f => ({ ...f, account_no: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Nama Pemilik</label>
                <input className="w-full border rounded-lg px-3 py-2 text-sm outline-none"
                  value={form.account_name} onChange={e => setForm(f => ({ ...f, account_name: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Saldo Awal</label>
                <input type="number" className="w-full border rounded-lg px-3 py-2 text-sm outline-none"
                  value={form.opening_balance} onChange={e => setForm(f => ({ ...f, opening_balance: +e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Saldo Akhir (Buku Bank)</label>
                <input type="number" className="w-full border rounded-lg px-3 py-2 text-sm outline-none"
                  value={form.closing_balance} onChange={e => setForm(f => ({ ...f, closing_balance: +e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button data-testid="btn-save-session" size="sm" onClick={createSession}>Buat Sesi</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowCreate(false)}>Batal</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {loading ? <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin" /></div> : (
        <>
          {items.length === 0 && (
            <div className="text-center py-12 text-muted-foreground">
              <ArrowLeftRight className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>Belum ada sesi rekonsiliasi.</p>
            </div>
          )}
          <div className="space-y-2">
            {items.map(s => {
              const cfg = STATUS_CFG[s.status] || STATUS_CFG.draft;
              const pct = s.total_bank_txns > 0 ? Math.round(s.matched_count / s.total_bank_txns * 100) : 0;
              return (
                <Card key={s.id} data-testid={`session-${s.id}`}
                  className="hover:shadow-sm transition-shadow cursor-pointer"
                  onClick={() => onOpen(s)}>
                  <CardContent className="pt-4 pb-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-sm">{s.period}</span>
                          <span className="text-sm">{s.bank_name} {s.account_no && `· ${s.account_no}`}</span>
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${cfg.color}`}>{cfg.label}</span>
                        </div>
                        <div className="flex items-center gap-3 mt-1.5">
                          <div className="flex-1 bg-muted rounded-full h-1.5">
                            <div className="bg-primary h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-xs text-muted-foreground whitespace-nowrap">
                            {s.matched_count}/{s.total_bank_txns} matched ({pct}%)
                          </span>
                        </div>
                        {s.difference !== 0 && (
                          <p className="text-xs text-red-600 mt-1">Selisih: {fmt(s.difference)}</p>
                        )}
                      </div>
                      <button data-testid={`btn-delete-session-${s.id}`}
                        onClick={e => { e.stopPropagation(); deleteSession(s.id); }}
                        className="p-1.5 rounded hover:bg-red-100 text-muted-foreground hover:text-red-600">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
          <PaginationBar total={total} skip={skip} limit={LIMIT} onPageChange={setSkip} />
        </>
      )}
    </div>
  );
}

// ── Session Detail (Transaction Matching) ───────────────────────────────────
function SessionDetail({ session, headers, onBack }) {
  const { toast } = useToast();
  const csvInputRef = useRef(null);
  const [txns, setTxns] = useState([]);
  const [glEntries, setGlEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showImport, setShowImport] = useState(false);
  const [showAddTxn, setShowAddTxn] = useState(false);
  const [selectedTxn, setSelectedTxn] = useState(null);
  const [filterMatched, setFilterMatched] = useState(null);
  const [approving, setApproving] = useState(false);
  const [autoMatching, setAutoMatching] = useState(false);
  const [csvImporting, setCsvImporting] = useState(false);
  const [importTab, setImportTab] = useState('file'); // 'file' | 'paste'
  const [txnForm, setTxnForm] = useState({ txn_date: '', description: '', reference: '', amount: 0, type: 'debit' });
  const [bulkText, setBulkText] = useState('');
  const [csvDragOver, setCsvDragOver] = useState(false);
  const LIMIT = 30;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { skip, limit: LIMIT };
      if (filterMatched !== null) params.matched = filterMatched;
      const [txRes, glRes] = await Promise.all([
        axios.get(`${API}/api/finance/bank-recon/sessions/${session.id}/transactions`, { headers, params }),
        axios.get(`${API}/api/finance/bank-recon/gl-entries`, { headers, params: { period: session.period } }),
      ]);
      setTxns(txRes.data.items || []);
      setTotal(txRes.data.total || 0);
      setGlEntries(glRes.data.items || []);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [headers, session.id, session.period, skip, filterMatched]);

  useEffect(() => { load(); }, [load]);

  const addTxn = async () => {
    if (!txnForm.txn_date || !txnForm.amount) { toast({ title: 'Isi tanggal dan nominal.', variant: 'destructive' }); return; }
    try {
      await axios.post(`${API}/api/finance/bank-recon/sessions/${session.id}/transactions`, txnForm, { headers });
      toast({ title: 'Transaksi ditambahkan.' });
      setShowAddTxn(false);
      setTxnForm({ txn_date: '', description: '', reference: '', amount: 0, type: 'debit' });
      load();
    } catch (e) { toast({ title: e.response?.data?.detail || 'Gagal.', variant: 'destructive' }); }
  };

  const importBulk = async () => {
    try {
      const lines = bulkText.trim().split('\n').filter(Boolean);
      const transactions = lines.map(line => {
        const parts = line.split(',').map(s => s.trim());
        return { txn_date: parts[0], description: parts[1] || '', amount: parseFloat(parts[2]) || 0, type: parts[3] || 'debit', reference: parts[4] || '' };
      });
      const { data } = await axios.post(`${API}/api/finance/bank-recon/sessions/${session.id}/import-bulk`, { transactions }, { headers });
      toast({ title: data.message });
      setShowImport(false);
      setBulkText('');
      load();
    } catch (e) { toast({ title: e.response?.data?.detail || 'Gagal import.', variant: 'destructive' }); }
  };

  const importCsvFile = async (file) => {
    if (!file) return;
    setCsvImporting(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const { data } = await axios.post(
        `${API}/api/finance/bank-recon/sessions/${session.id}/import-csv`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } }
      );
      toast({ title: data.message });
      setShowImport(false);
      load();
    } catch (e) {
      toast({ title: e.response?.data?.detail || 'Gagal import CSV.', variant: 'destructive' });
    } finally {
      setCsvImporting(false);
    }
  };

  const handleCsvDrop = (e) => {
    e.preventDefault();
    setCsvDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) importCsvFile(file);
  };

  const autoMatch = async () => {
    setAutoMatching(true);
    try {
      const { data } = await axios.post(
        `${API}/api/finance/bank-recon/sessions/${session.id}/auto-match`,
        {},
        { headers }
      );
      toast({ title: data.message });
      load();
    } catch (e) {
      toast({ title: e.response?.data?.detail || 'Auto-match gagal.', variant: 'destructive' });
    } finally {
      setAutoMatching(false);
    }
  };

  const matchTxn = async (txn, glEntry) => {
    try {
      await axios.post(`${API}/api/finance/bank-recon/sessions/${session.id}/match`, {
        txn_id: txn.id, gl_entry_id: glEntry.id, gl_ref: glEntry.reference || glEntry.description || '',
      }, { headers });
      toast({ title: 'Transaksi berhasil dicocokkan.' });
      setSelectedTxn(null);
      load();
    } catch (e) { toast({ title: e.response?.data?.detail || 'Gagal.', variant: 'destructive' }); }
  };

  const unmatchTxn = async (txn) => {
    try {
      await axios.post(`${API}/api/finance/bank-recon/sessions/${session.id}/unmatch`, { txn_id: txn.id }, { headers });
      load();
    } catch (e) { toast({ title: 'Gagal.', variant: 'destructive' }); }
  };

  const deleteTxn = async (id) => {
    try {
      await axios.delete(`${API}/api/finance/bank-recon/sessions/${session.id}/transactions/${id}`, { headers });
      load();
    } catch (e) { toast({ title: 'Gagal.', variant: 'destructive' }); }
  };

  const approve = async () => {
    setApproving(true);
    try {
      await axios.post(`${API}/api/finance/bank-recon/sessions/${session.id}/approve`, {}, { headers });
      toast({ title: 'Rekonsiliasi disetujui!' });
      onBack();
    } catch (e) {
      toast({ title: e.response?.data?.detail || 'Gagal approve.', variant: 'destructive' });
    } finally { setApproving(false); }
  };

  const cfg = STATUS_CFG[session.status] || STATUS_CFG.draft;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <Button variant="outline" size="sm" onClick={onBack}>&larr; Kembali</Button>
        <div className="flex-1">
          <h3 className="font-semibold">{session.period} — {session.bank_name} {session.account_no}</h3>
          <p className="text-xs text-muted-foreground">{session.account_name}</p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${cfg.color}`}>{cfg.label}</span>
        {session.status !== 'approved' && (
          <Button data-testid="btn-approve" size="sm" onClick={approve} disabled={approving}
            className="bg-green-600 hover:bg-green-700 text-foreground">
            {approving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><CheckCircle2 className="w-4 h-4 mr-1" /> Approve</>}
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total Transaksi', val: session.total_bank_txns || 0 },
          { label: 'Matched', val: session.matched_count || 0, color: 'text-green-600' },
          { label: 'Unmatched', val: session.unmatched_count || 0, color: session.unmatched_count > 0 ? 'text-red-600' : '' },
          { label: 'Selisih', val: fmt(session.difference || 0), color: session.difference !== 0 ? 'text-red-600' : 'text-green-600' },
        ].map((s, i) => (
          <Card key={i}><CardContent className="pt-3 pb-2">
            <p className={`text-lg font-bold ${s.color || ''}`}>{s.val}</p>
            <p className="text-xs text-muted-foreground">{s.label}</p>
          </CardContent></Card>
        ))}
      </div>

      {/* Actions */}
      {session.status !== 'approved' && (
        <div className="flex gap-2 flex-wrap">
          <Button size="sm" variant="outline" onClick={() => setShowAddTxn(v => !v)}>
            <Plus className="w-4 h-4 mr-1" /> Tambah Manual
          </Button>
          <Button size="sm" variant="outline" onClick={() => setShowImport(v => !v)}>
            <Upload className="w-4 h-4 mr-1" /> Import CSV
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={autoMatch}
            disabled={autoMatching}
            data-testid="btn-auto-match"
            className="border-blue-300 text-blue-700 hover:bg-blue-50"
          >
            {autoMatching
              ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Auto-Match...</>
              : <><ArrowLeftRight className="w-4 h-4 mr-1" /> Auto-Match</>}
          </Button>
        </div>
      )}

      {/* Add single transaction form */}
      {showAddTxn && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="pt-4 space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-medium mb-1 block">Tanggal</label>
                <input type="date" data-testid="input-txn-date"
                  className="w-full border rounded-lg px-2 py-1.5 text-sm outline-none"
                  value={txnForm.txn_date} onChange={e => setTxnForm(f => ({ ...f, txn_date: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Nominal</label>
                <input type="number" data-testid="input-txn-amount"
                  className="w-full border rounded-lg px-2 py-1.5 text-sm outline-none"
                  value={txnForm.amount} onChange={e => setTxnForm(f => ({ ...f, amount: +e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Tipe</label>
                <select className="w-full border rounded-lg px-2 py-1.5 text-sm outline-none"
                  value={txnForm.type} onChange={e => setTxnForm(f => ({ ...f, type: e.target.value }))}>
                  <option value="debit">Debit (Masuk)</option>
                  <option value="credit">Kredit (Keluar)</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Keterangan</label>
                <input className="w-full border rounded-lg px-2 py-1.5 text-sm outline-none"
                  value={txnForm.description} onChange={e => setTxnForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium mb-1 block">Referensi</label>
                <input className="w-full border rounded-lg px-2 py-1.5 text-sm outline-none"
                  value={txnForm.reference} onChange={e => setTxnForm(f => ({ ...f, reference: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button data-testid="btn-add-txn" size="sm" onClick={addTxn}>Tambah</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowAddTxn(false)}>Batal</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Import CSV Panel */}
      {showImport && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Import Bank Statement CSV</CardTitle>
              <div className="flex gap-1 text-xs">
                <button onClick={() => setImportTab('file')}
                  className={`px-3 py-1 rounded-full font-medium transition-colors ${importTab === 'file' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
                  File Upload
                </button>
                <button onClick={() => setImportTab('paste')}
                  className={`px-3 py-1 rounded-full font-medium transition-colors ${importTab === 'paste' ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
                  Paste CSV
                </button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {importTab === 'file' ? (
              <>
                {/* Drag & drop area */}
                <div
                  onDragOver={(e) => { e.preventDefault(); setCsvDragOver(true); }}
                  onDragLeave={() => setCsvDragOver(false)}
                  onDrop={handleCsvDrop}
                  onClick={() => csvInputRef.current?.click()}
                  data-testid="csv-drop-zone"
                  className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                    csvDragOver
                      ? 'border-primary bg-primary/10'
                      : 'border-amber-300 hover:border-primary hover:bg-white'
                  }`}
                >
                  {csvImporting ? (
                    <div className="flex flex-col items-center gap-2">
                      <Loader2 className="w-8 h-8 animate-spin text-primary" />
                      <p className="text-sm text-muted-foreground">Mengimpor data...</p>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-2">
                      <Upload className="w-8 h-8 text-amber-600" />
                      <p className="text-sm font-medium">Drag & drop file CSV</p>
                      <p className="text-xs text-muted-foreground">atau klik untuk browse</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Format: tanggal, keterangan, debit/kredit, referensi<br/>
                        Mendukung format BCA, Mandiri, BNI, BRI, dll.
                      </p>
                    </div>
                  )}
                </div>
                <input
                  ref={csvInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={e => { const f = e.target.files?.[0]; if (f) importCsvFile(f); }}
                  data-testid="input-csv-file"
                />
              </>
            ) : (
              <>
                <p className="text-xs text-muted-foreground">Format: tanggal, keterangan, nominal, tipe (debit/kredit), referensi</p>
                <p className="text-xs text-muted-foreground">Contoh: 2026-05-01, Transfer dari Client A, 5000000, debit, TRF001</p>
                <textarea className="w-full border rounded-lg px-3 py-2 text-xs outline-none font-mono resize-none"
                  rows={6} value={bulkText} onChange={e => setBulkText(e.target.value)}
                  placeholder="2026-05-01, Transfer Client A, 5000000, debit, TRF001&#10;2026-05-03, Bayar Supplier, 2000000, credit, INV002" />
                <div className="flex gap-2">
                  <Button data-testid="btn-import-bulk" size="sm" onClick={importBulk}>Import</Button>
                  <Button size="sm" variant="ghost" onClick={() => setShowImport(false)}>Batal</Button>
                </div>
              </>
            )}
            <Button size="sm" variant="ghost" className="w-full" onClick={() => setShowImport(false)}>Tutup</Button>
          </CardContent>
        </Card>
      )}

      {/* Filter */}
      <div className="flex gap-1">
        {[
          { label: 'Semua', val: null },
          { label: 'Belum Match', val: false },
          { label: 'Sudah Match', val: true },
        ].map(f => (
          <button key={String(f.val)} onClick={() => { setFilterMatched(f.val); setSkip(0); }}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors
              ${filterMatched === f.val ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Transactions table */}
      {loading ? (
        <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : (
        <>
          {txns.length === 0 && (
            <div className="text-center py-10 text-muted-foreground">
              <FileText className="w-10 h-10 mx-auto mb-2 opacity-30" />
              <p>Belum ada transaksi. Tambah manual atau import.</p>
            </div>
          )}
          <div className="space-y-1.5">
            {txns.map(txn => (
              <div key={txn.id} data-testid={`txn-${txn.id}`}
                className={`rounded-lg border p-3 transition-all ${txn.is_matched ? 'bg-green-50 border-green-200' : 'bg-background hover:shadow-sm'}`}>
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${txn.type === 'debit' ? 'bg-green-500' : 'bg-red-500'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-muted-foreground">{txn.txn_date}</span>
                      <span className="text-sm font-medium truncate">{txn.description || '—'}</span>
                      {txn.reference && <span className="text-xs text-muted-foreground">#{txn.reference}</span>}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className={`font-semibold text-sm ${txn.type === 'debit' ? 'text-green-700' : 'text-red-700'}`}>
                        {txn.type === 'debit' ? '+' : '-'}{fmt(txn.amount)}
                      </span>
                      {txn.is_matched && (
                        <span className="text-xs text-green-600 flex items-center gap-1">
                          <Check className="w-3 h-3" /> Matched: {txn.match_ref}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    {!txn.is_matched && session.status !== 'approved' && (
                      <button data-testid={`btn-match-${txn.id}`}
                        onClick={() => setSelectedTxn(selectedTxn?.id === txn.id ? null : txn)}
                        className={`p-1.5 rounded text-xs font-medium transition-colors
                          ${selectedTxn?.id === txn.id ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-primary/10'}`}>
                        <LinkIcon className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {txn.is_matched && session.status !== 'approved' && (
                      <button onClick={() => unmatchTxn(txn)}
                        className="p-1.5 rounded hover:bg-amber-100 text-muted-foreground hover:text-amber-600">
                        <Unlink className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {session.status !== 'approved' && (
                      <button onClick={() => deleteTxn(txn.id)}
                        className="p-1.5 rounded hover:bg-red-100 text-muted-foreground hover:text-red-600">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* GL entry picker */}
                {selectedTxn?.id === txn.id && (
                  <div className="mt-3 pl-4 border-l-2 border-primary/30">
                    <p className="text-xs font-semibold mb-2 text-primary">Pilih GL Entry untuk dicocokkan:</p>
                    <div className="max-h-48 overflow-y-auto space-y-1">
                      {glEntries.length === 0 && (
                        <p className="text-xs text-muted-foreground">Tidak ada GL entry untuk periode ini.</p>
                      )}
                      {glEntries.map(gl => (
                        <button key={gl.id} onClick={() => matchTxn(txn, gl)}
                          className="w-full text-left p-2 rounded hover:bg-primary/10 border text-xs">
                          <div className="flex justify-between">
                            <span>{gl.date} · {gl.description}</span>
                            <span className="font-medium">{fmt(gl.amount || gl.debit || gl.credit)}</span>
                          </div>
                          {gl.reference && <span className="text-muted-foreground">#{gl.reference}</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
          <PaginationBar total={total} skip={skip} limit={LIMIT} onPageChange={setSkip} />
        </>
      )}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────
export default function BankReconciliation({ user, headers }) {
  const [activeSession, setActiveSession] = useState(null);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
          <ArrowLeftRight className="w-5 h-5 text-blue-700" />
        </div>
        <div>
          <h2 className="text-lg font-bold">Bank Reconciliation</h2>
          <p className="text-xs text-muted-foreground">Cocokkan mutasi bank dengan transaksi sistem</p>
        </div>
      </div>

      {activeSession ? (
        <SessionDetail
          session={activeSession}
          headers={headers}
          onBack={() => setActiveSession(null)}
        />
      ) : (
        <SessionList headers={headers} onOpen={setActiveSession} />
      )}
    </div>
  );
}
