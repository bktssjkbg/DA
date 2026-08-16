# backups/f10_removed — arsip modul yang DIHAPUS di F10

## Kenapa berkasnya berakhiran `.jsx.bak`, bukan `.jsx`

`TokoProductCatalogModule.jsx` dihapus dari `frontend/src/components/erp/` pada F10
sesudah redirect F4.4 (`?module=toko-products` → **Manajemen Katalog Produk**)
terbukti bekerja. Salinannya disimpan di sini sebagai arsip baca-saja.

Selama salinan itu masih berakhiran `.jsx`, ia IKUT dipindai **Import Validation**
milik gate lint platform. Import relatifnya (`import { PageHeader } from './moduleAtoms'`)
tidak bisa di-resolve dari folder ini, sehingga:

```
engine_success = oxlint_success AND import_success   ← import_success = False
```

⇒ arm OXLINT pada cakupan **root repo** melaporkan `engine_success=False`, dan gate
pra-penyelesaian platform **menolak tool `finish` / `ask_human`**. Artinya: sebuah
sesi bisa menyelesaikan seluruh pekerjaannya lalu tidak bisa menyerahkan hasilnya —
karena satu berkas arsip yang tidak pernah masuk bundel.

Diukur (2026-08-14, sebelum perbaikan):

| cakupan | engine_success | temuan Import Validation |
|---|---|---|
| `/app` (root) | **False** | `backups/f10_removed/TokoProductCatalogModule.jsx:11 — Cannot resolve import './moduleAtoms'` |
| `/app/frontend` | True | bersih |
| `/app/mobile` | True | bersih |

Sesudah diganti menjadi `.jsx.bak`: **INV-LINT-01 HIJAU** (arsipnya tetap utuh dan
bisa dibaca; ia hanya berhenti berpura-pura menjadi kode aplikasi).

## Aturan untuk agen berikutnya

**Mengarsipkan modul = pindahkan berkasnya KE LUAR ekstensi JS**, atau perbaiki
import relatifnya. Memindahkan `.jsx` apa adanya ke folder mana pun di dalam
`/app` akan mengulang kelas bug ini. Dijaga guardrail BLOCKING **INV-LINT-01**
(`scripts/guardrails/verify_platform_lint_engine.py`).

Riwayat lengkap berkas ini tetap ada di git (`git log --follow`).
