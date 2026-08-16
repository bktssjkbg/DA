import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Shirt, Plus, Search, Edit2, Trash2, ImagePlus, X, Package, Loader2 } from 'lucide-react';
import { GlassCard } from '@/components/ui/glass';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { PageHeader } from './moduleAtoms';
import { formatRupiah } from '@/lib/format';

// ── Constants ────────────────────────────────────────────────────────────────
const STATUS_FILTERS = [
  { id: 'all', label: 'Semua' },
  { id: 'active', label: 'Aktif' },
  { id: 'inactive', label: 'Non-Aktif' },
];

const fmtIDR = formatRupiah;

const emptyForm = {
  sku: '',
  name: '',
  description: '',
  category: '',
  price: 0,
  original_price: 0,
  platform_price: 0,
  stock_quantity: 0,
  stock_alert_threshold: 10,
  weight_gram: 0,
  variant_info: '',
  variant_id: '',
  is_active: true,
  platform_url: '',
  images: [],
  tags: [],
};

// ── Helpers: dual-shape tolerant (marketing + legacy back-compat) ───────────
// Use these to read fields from product docs that may be in either shape
const readProduct = (p) => {
  if (!p) return null;
  return {
    id: p.id,
    sku: p.sku || p.sku_code || '',
    name: p.name || '',
    description: p.description || '',
    category: p.category || '',
    price: Number(p.price ?? p.base_price ?? 0),
    original_price: Number(p.original_price ?? p.cost_price ?? 0),
    platform_price: Number(p.platform_price ?? 0),
    stock_quantity: Number(p.stock_quantity ?? p.stock_total ?? 0),
    stock_alert_threshold: Number(p.stock_alert_threshold ?? 10),
    stock_status: p.stock_status || (Number(p.stock_quantity ?? p.stock_total ?? 0) <= 0 ? 'out_of_stock' : 'in_stock'),
    weight_gram: Number(p.weight_gram ?? p.weight_grams ?? 0),
    variant_info: p.variant_info || '',
    is_active: p.is_active !== undefined ? !!p.is_active : (p.status === 'active'),
    platform_url: p.platform_url || '',
    images: Array.isArray(p.images) && p.images.length ? p.images : (Array.isArray(p.photos) ? p.photos : []),
    tags: Array.isArray(p.tags) ? p.tags : [],
  };
};

export default function TokoProductCatalogModule({ token }) {
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);
  const [catalogId, setCatalogId] = useState(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState(null); // {data} for edit; {} for create
  const [saving, setSaving] = useState(false);

  // Resolve "Toko Legacy" catalog ID on mount
  useEffect(() => {
    const resolveCatalog = async () => {
      setCatalogLoading(true);
      try {
        const r = await fetch('/api/marketing/catalogs', { headers });
        if (!r.ok) throw new Error('Gagal load catalogs');
        const d = await r.json();
        const list = d.catalogs || [];
        // Find the auto-created Toko Legacy catalog
        const tokoLegacy = list.find((c) => c._toko_legacy === true) ||
                           list.find((c) => (c.name || '').toLowerCase().includes('toko legacy'));
        if (tokoLegacy) {
          setCatalogId(tokoLegacy.id);
        } else {
          toast.error('Catalog "Toko Legacy" tidak ditemukan. Hubungi admin.');
        }
      } catch (e) {
        toast.error(e.message);
      } finally {
        setCatalogLoading(false);
      }
    };
    resolveCatalog();
  }, [headers]);

  const load = useCallback(async () => {
    if (!catalogId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter === 'active') params.set('is_active', 'true');
      if (filter === 'inactive') params.set('is_active', 'false');
      if (search) params.set('search', search);
      params.set('limit', '500');
      const r = await fetch(`/api/marketing/catalogs/${catalogId}/items?${params}`, { headers });
      if (r.ok) {
        const d = await r.json();
        setProducts((d.items || []).map(readProduct));
      }
    } finally {
      setLoading(false);
    }
  }, [filter, search, headers, catalogId]);

  useEffect(() => { load(); }, [load]);

  const save = async (form, id) => {
    if (!catalogId) {
      toast.error('Catalog belum siap');
      return;
    }
    setSaving(true);
    try {
      const body = {
        sku: form.sku,
        name: form.name,
        description: form.description || '',
        category: form.category || '',
        price: Number(form.price || 0),
        original_price: Number(form.original_price || 0),
        platform_price: Number(form.platform_price || 0),
        stock_quantity: Number(form.stock_quantity || 0),
        stock_alert_threshold: Number(form.stock_alert_threshold || 10),
        weight_gram: Number(form.weight_gram || 0),
        variant_info: form.variant_info || '',
        variant_id: form.variant_id || '',
        is_active: !!form.is_active,
        platform_url: form.platform_url || '',
        images: form.images || [],
        tags: form.tags || [],
      };
      let r, d;
      if (id) {
        r = await fetch(`/api/marketing/catalogs/${catalogId}/items/${id}`, {
          method: 'PUT',
          headers,
          body: JSON.stringify(body),
        });
      } else {
        r = await fetch(`/api/marketing/catalogs/${catalogId}/items`, {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
        });
      }
      d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Gagal');
      toast.success(id ? 'Produk diperbarui' : 'Produk dibuat');
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (p) => {
    if (!window.confirm(`Hapus produk ${p.sku}?`)) return;
    const r = await fetch(`/api/marketing/catalogs/${catalogId}/items/${p.id}`, {
      method: 'DELETE',
      headers,
    });
    if (r.ok) {
      toast.success('Dihapus');
      load();
    } else {
      const d = await r.json();
      toast.error(d.detail || 'Gagal hapus');
    }
  };

  if (catalogLoading) {
    return (
      <div className="p-6 text-center" data-testid="toko-product-catalog-loading">
        <Loader2 className="w-6 h-6 animate-spin mx-auto text-foreground/40" />
        <p className="text-sm text-foreground/55 mt-2">Memuat catalog...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" data-testid="toko-product-catalog">
      <PageHeader
        title="Katalog Produk Toko"
        description="Master SKU, harga, stok (Marketing SSOT)"
        icon={Shirt}
        actions={
          <Button
            size="sm"
            onClick={() => setEditing({})}
            className="gap-1.5"
            data-testid="toko-product-create-btn"
            disabled={!catalogId}
          >
            <Plus className="w-3.5 h-3.5" /> Produk Baru
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1.5">
          {STATUS_FILTERS.map((f) => (
            <Button
              key={f.id}
              size="sm"
              variant={filter === f.id ? 'default' : 'outline'}
              onClick={() => setFilter(f.id)}
              data-testid={`toko-product-filter-${f.id}`}
            >
              {f.label}
            </Button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-foreground/40" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari SKU / nama produk..."
            className="w-full rounded-lg border border-foreground/10 bg-foreground/5 pl-8 pr-3 py-1.5 text-sm focus:outline-none focus:border-[hsl(var(--primary))]/60"
            data-testid="toko-product-search"
          />
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 animate-pulse">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-56 rounded-xl bg-foreground/[0.05]" />)}
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-14 rounded-xl border border-dashed border-foreground/10">
          <Package className="w-10 h-10 mx-auto text-foreground/30 mb-2" />
          <p className="text-sm text-foreground/50">Belum ada produk. Klik &quot;Produk Baru&quot; untuk mulai.</p>
        </div>
      ) : (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          data-testid="toko-product-grid"
        >
          {products.map((p) => (
            <GlassCard
              key={p.id}
              className="overflow-hidden flex flex-col"
              data-testid={`toko-product-card-${p.id}`}
            >
              <div className="aspect-square bg-foreground/[0.04] flex items-center justify-center relative overflow-hidden">
                {p.images?.[0] ? (
                  <img src={p.images[0]} alt={p.name} className="w-full h-full object-cover" />
                ) : (
                  <Shirt className="w-10 h-10 text-foreground/20" />
                )}
                <div className="absolute top-2 right-2">
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded uppercase font-medium ${
                      p.is_active
                        ? 'bg-emerald-100 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-300'
                        : 'bg-foreground/20 text-foreground/60'
                    }`}
                  >
                    {p.is_active ? 'aktif' : 'non-aktif'}
                  </span>
                </div>
                {p.stock_status === 'low_stock' && (
                  <div className="absolute top-2 left-2">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-500/20 text-amber-600 dark:text-amber-300 uppercase">
                      Low Stock
                    </span>
                  </div>
                )}
                {p.stock_status === 'out_of_stock' && (
                  <div className="absolute top-2 left-2">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-500/20 text-red-600 dark:text-red-300 uppercase">
                      Habis
                    </span>
                  </div>
                )}
              </div>
              <div className="p-3 space-y-1.5 flex-1 flex flex-col">
                <div className="font-mono text-[10px] text-foreground/55 flex items-center gap-1">
                  {p.sku}
                </div>
                <div className="text-sm font-medium line-clamp-2">{p.name}</div>
                <div className="text-xs text-foreground/55">{p.category || '—'}</div>
                {p.variant_info && (
                  <div className="text-xs text-foreground/45 line-clamp-1">{p.variant_info}</div>
                )}
                <div className="flex items-center justify-between mt-auto pt-2">
                  <div>
                    <div className="text-sm font-bold tabular-nums">{fmtIDR(p.price)}</div>
                    <div className="text-xs text-foreground/55">Stok {p.stock_quantity}</div>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="w-7 h-7"
                      onClick={() => setEditing({ data: p })}
                      data-testid={`toko-product-edit-${p.id}`}
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="w-7 h-7 text-red-700 dark:text-red-400 hover:bg-red-100 dark:bg-red-500/15"
                      onClick={() => remove(p)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      {editing && (
        <ProductEditor
          product={editing.data}
          catalogId={catalogId}
          headers={headers}
          token={token}
          onClose={() => setEditing(null)}
          onSave={save}
          saving={saving}
        />
      )}
    </div>
  );
}

function ProductEditor({ product, catalogId, headers, token, onClose, onSave, saving }) {
  const isEdit = Boolean(product);
  const [form, setForm] = useState(() => product ? {
    ...emptyForm,
    sku: product.sku || '',
    name: product.name || '',
    description: product.description || '',
    category: product.category || '',
    price: product.price || 0,
    original_price: product.original_price || 0,
    platform_price: product.platform_price || 0,
    stock_quantity: product.stock_quantity || 0,
    stock_alert_threshold: product.stock_alert_threshold || 10,
    weight_gram: product.weight_gram || 0,
    variant_info: product.variant_info || '',
    variant_id: product.variant_id || '',
    is_active: product.is_active !== undefined ? !!product.is_active : true,
    platform_url: product.platform_url || '',
    images: Array.isArray(product.images) ? product.images : [],
    tags: Array.isArray(product.tags) ? product.tags : [],
  } : { ...emptyForm });
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  // Fase 3b: varian produksi internal utk penautan stok Toko<->FG
  const [prodVariants, setProdVariants] = useState([]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/api/rahaza/variants', { headers: { Authorization: `Bearer ${token}` } });
        if (r.ok && !cancelled) setProdVariants(await r.json());
      } catch (_e) { /* silent */ }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const handlePhotoUpload = async (e) => {
    if (!isEdit) {
      toast.error('Simpan produk dulu sebelum upload foto');
      if (fileRef.current) fileRef.current.value = '';
      return;
    }
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    for (const f of files) {
      if (!f.type.startsWith('image/')) {
        toast.error(`${f.name} bukan gambar`);
        continue;
      }
      if (f.size > 5 * 1024 * 1024) {
        toast.error(`${f.name} > 5MB`);
        continue;
      }
      try {
        const fd = new FormData();
        fd.append('file', f);
        const r = await fetch(
          `/api/marketing/catalogs/${catalogId}/items/${product.id}/photos`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: fd,
          }
        );
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || 'Upload gagal');
        set({ images: [...form.images, d.url] });
      } catch (err) {
        toast.error(`${f.name}: ${err.message}`);
      }
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const removePhoto = async (url) => {
    if (isEdit) {
      try {
        await fetch(
          `/api/marketing/catalogs/${catalogId}/items/${product.id}/photos/remove`,
          {
            method: 'POST',
            headers,
            body: JSON.stringify({ url }),
          }
        );
      } catch (e) {
        /* ignore */
      }
    }
    set({ images: form.images.filter((u) => u !== url) });
  };

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="toko-product-editor">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shirt className="w-4 h-4 text-pink-600 dark:text-pink-400" /> {isEdit ? 'Edit Produk' : 'Produk Baru'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Basic */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">SKU *</Label>
              <Input
                value={form.sku}
                onChange={(e) => set({ sku: e.target.value.toUpperCase() })}
                placeholder="BLS-LINEN-001"
                disabled={isEdit}
                data-testid="toko-product-sku"
              />
            </div>
            <div>
              <Label className="text-xs">Kategori</Label>
              <Input
                value={form.category}
                onChange={(e) => set({ category: e.target.value })}
                placeholder="Blouse, Dress..."
              />
            </div>
          </div>
          <div>
            <Label className="text-xs">Nama Produk *</Label>
            <Input
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              placeholder="Blouse Linen Premium..."
              data-testid="toko-product-name"
            />
          </div>
          <div>
            <Label className="text-xs">Deskripsi</Label>
            <Textarea
              value={form.description}
              onChange={(e) => set({ description: e.target.value })}
              rows={3}
            />
          </div>
          <div>
            <Label className="text-xs">Varian (opsional)</Label>
            <Input
              value={form.variant_info}
              onChange={(e) => set({ variant_info: e.target.value })}
              placeholder="Warna: Merah, Size: L"
              data-testid="toko-product-variant"
            />
          </div>
          <div>
            <Label className="text-xs">Tautkan Varian Produksi (opsional)</Label>
            <Select
              value={form.variant_id || 'none'}
              onValueChange={(val) => {
                if (val === 'none') { set({ variant_id: '' }); return; }
                const v = prodVariants.find((x) => x.id === val);
                set({
                  variant_id: val,
                  sku: (form.sku && form.sku.trim()) ? form.sku : (v?.sku || ''),
                  variant_info: form.variant_info || (v ? `Warna: ${v.color_name}, Size: ${v.size_code}` : ''),
                });
              }}
            >
              <SelectTrigger data-testid="toko-variant-selector">
                <SelectValue placeholder="— Tidak ditautkan —" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">— Tidak ditautkan —</SelectItem>
                {prodVariants.map((v) => (
                  <SelectItem key={v.id} value={v.id}>{v.sku} · {v.color_name} {v.size_code}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-[10px] text-foreground/45 mt-0.5">Tautkan ke SKU varian produksi internal agar stok Toko ↔ FG selaras.</p>
          </div>

          {/* Pricing */}
          <div className="rounded-lg border border-foreground/10 p-3 space-y-2">
            <div className="text-xs font-medium uppercase tracking-wider text-foreground/55">Pricing</div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Harga Jual (Rp)</Label>
                <Input
                  type="number"
                  value={form.price}
                  onChange={(e) => set({ price: e.target.value })}
                  data-testid="toko-product-price"
                />
              </div>
              <div>
                <Label className="text-xs">HPP / Modal (Rp)</Label>
                <Input
                  type="number"
                  value={form.original_price}
                  onChange={(e) => set({ original_price: e.target.value })}
                />
              </div>
              <div>
                <Label className="text-xs">Harga Platform (Rp)</Label>
                <Input
                  type="number"
                  value={form.platform_price}
                  onChange={(e) => set({ platform_price: e.target.value })}
                />
              </div>
            </div>
            <div>
              <Label className="text-xs">Berat (gram)</Label>
              <Input
                type="number"
                value={form.weight_gram}
                onChange={(e) => set({ weight_gram: e.target.value })}
              />
            </div>
          </div>

          {/* Stock */}
          <div className="rounded-lg border border-foreground/10 p-3 space-y-2">
            <div className="text-xs font-medium uppercase tracking-wider text-foreground/55">Stok</div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Stok Tersedia</Label>
                <Input
                  type="number"
                  value={form.stock_quantity}
                  onChange={(e) => set({ stock_quantity: e.target.value })}
                  data-testid="toko-product-stock"
                />
              </div>
              <div>
                <Label className="text-xs">Threshold Low-Stock</Label>
                <Input
                  type="number"
                  value={form.stock_alert_threshold}
                  onChange={(e) => set({ stock_alert_threshold: e.target.value })}
                />
              </div>
            </div>
          </div>

          {/* Status */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Status</Label>
              <Select
                value={form.is_active ? 'active' : 'inactive'}
                onValueChange={(v) => set({ is_active: v === 'active' })}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Aktif (Tampil)</SelectItem>
                  <SelectItem value="inactive">Non-Aktif</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Platform URL (opsional)</Label>
              <Input
                value={form.platform_url}
                onChange={(e) => set({ platform_url: e.target.value })}
                placeholder="https://shopee.co.id/..."
              />
            </div>
          </div>

          {/* Photos */}
          <div className="rounded-lg border border-foreground/10 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-xs font-medium uppercase tracking-wider text-foreground/55">Foto Produk</div>
              {isEdit ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                  className="h-7 text-xs gap-1"
                  data-testid="toko-product-upload-photo"
                >
                  {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <ImagePlus className="w-3 h-3" />}
                  Upload
                </Button>
              ) : (
                <span className="text-[10px] text-foreground/45 italic">Simpan produk dulu</span>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                onChange={handlePhotoUpload}
                className="hidden"
              />
            </div>
            {form.images.length === 0 ? (
              <p className="text-xs text-foreground/45">Belum ada foto.</p>
            ) : (
              <div className="grid grid-cols-4 gap-2">
                {form.images.map((url) => (
                  <div
                    key={url}
                    className="relative aspect-square rounded-lg border border-foreground/10 overflow-hidden bg-foreground/[0.04]"
                  >
                    <img src={url} alt="" className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => removePhoto(url)}
                      className="absolute top-1 right-1 w-5 h-5 rounded-full bg-foreground/50 text-foreground flex items-center justify-center hover:bg-red-500"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={saving}>Batal</Button>
          <Button
            onClick={() => onSave(form, product?.id)}
            disabled={saving || !form.sku || !form.name}
            data-testid="toko-product-save"
          >
            {saving && <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />}
            {isEdit ? 'Simpan' : 'Buat'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
