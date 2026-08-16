"""
pdf_common.py — Fondasi bersama untuk semua PDF surat/dokumen (branding + tanda tangan).

Menyediakan:
  - get_company_profile(db)  : profil perusahaan ternormalisasi (nama/alamat/logo/dll),
                               tahan terhadap drift skema lama (phone/email vs company_phone).
  - get_doc_settings(db, t)  : pengaturan PDF per jenis dokumen (logo on/off, header/footer,
                               konfigurasi blok tanda tangan) + default bila belum di-set.
  - resolve_signature_name() : tentukan nama penandatangan (custom / dari field data / kosong).
  - SUPPORTED_PDF_DOCS       : registry semua jenis surat + field tanda tangan yang tersedia.

Dipakai oleh generator PDF (payslip, surat jalan, dll) & modul pengaturan PDF.
"""
from datetime import datetime, timezone


# ── Registry jenis dokumen surat (untuk pengaturan + tanda tangan) ──────────────
# available_fields = key yang boleh dijadikan sumber "nama dari field data".
SUPPORTED_PDF_DOCS = {
    "payslip": {
        "label": "Slip Gaji (Payslip)",
        "group": "HR & Payroll",
        "available_fields": [
            {"key": "employee_name", "label": "Nama Karyawan"},
            {"key": "employee_code", "label": "Kode/ID Karyawan"},
            {"key": "run_number", "label": "No. Run Payroll"},
            {"key": "approved_by", "label": "Disetujui oleh (run)"},
        ],
        "default_signatures": [
            {"key": "approved", "label": "Disetujui oleh", "name_source": "custom",
             "custom_name": "", "field_key": "", "role_label": "HRD / Finance"},
            {"key": "received", "label": "Diterima oleh", "name_source": "field",
             "custom_name": "", "field_key": "employee_name", "role_label": "Karyawan"},
        ],
    },
    "delivery-note": {
        "label": "Surat Jalan (SSOT)",
        "group": "Gudang & Logistik",
        "available_fields": [
            {"key": "issued_by", "label": "Diterbitkan oleh"},
            {"key": "recipient_name", "label": "Nama Penerima (tujuan)"},
            {"key": "driver_name", "label": "Nama Sopir"},
            {"key": "sj_number", "label": "No. Surat Jalan"},
        ],
        "default_signatures": [
            {"key": "sender", "label": "Pengirim", "name_source": "field",
             "custom_name": "", "field_key": "issued_by", "role_label": "Gudang"},
            {"key": "driver", "label": "Pengangkut / Sopir", "name_source": "field",
             "custom_name": "", "field_key": "driver_name", "role_label": "Ekspedisi"},
            {"key": "receiver", "label": "Penerima", "name_source": "blank",
             "custom_name": "", "field_key": "recipient_name", "role_label": "Penerima"},
        ],
    },
    "invoice-maklon": {
        "label": "Invoice Maklon",
        "group": "Finance",
        "available_fields": [
            {"key": "client_name", "label": "Nama Klien"},
            {"key": "invoice_number", "label": "No. Invoice"},
        ],
        "default_signatures": [
            {"key": "issued", "label": "Hormat kami", "name_source": "custom",
             "custom_name": "", "field_key": "", "role_label": "Finance"},
        ],
    },
    "vendor-shipment": {
        "label": "Surat Jalan Vendor (POS lama)",
        "group": "Produksi (legacy)",
        "available_fields": [
            {"key": "vendor_name", "label": "Nama Vendor"},
            {"key": "shipment_number", "label": "No. Pengiriman"},
        ],
        "default_signatures": [
            {"key": "sender", "label": "Pengirim", "name_source": "custom", "custom_name": "", "field_key": "", "role_label": "Produksi"},
            {"key": "receiver", "label": "Penerima", "name_source": "field", "custom_name": "", "field_key": "vendor_name", "role_label": "Vendor"},
        ],
    },
    "buyer-shipment-dispatch": {
        "label": "Dispatch ke Buyer (POS lama)",
        "group": "Produksi (legacy)",
        "available_fields": [
            {"key": "buyer_name", "label": "Nama Buyer"},
            {"key": "shipment_number", "label": "No. Pengiriman"},
        ],
        "default_signatures": [
            {"key": "sender", "label": "Pengirim", "name_source": "custom", "custom_name": "", "field_key": "", "role_label": "Produksi"},
            {"key": "receiver", "label": "Penerima", "name_source": "field", "custom_name": "", "field_key": "buyer_name", "role_label": "Buyer"},
        ],
    },
    "production-po": {
        "label": "Surat Perintah Produksi (SPP)",
        "group": "Produksi",
        "available_fields": [
            {"key": "vendor_name", "label": "Nama Vendor/CMT"},
            {"key": "po_number", "label": "No. PO"},
        ],
        "default_signatures": [
            {"key": "prepared", "label": "Dibuat oleh", "name_source": "custom",
             "custom_name": "", "field_key": "", "role_label": "PPIC / Produksi"},
            {"key": "approved", "label": "Disetujui oleh", "name_source": "custom",
             "custom_name": "", "field_key": "", "role_label": "Manajer Produksi"},
            {"key": "received", "label": "Pelaksana", "name_source": "field",
             "custom_name": "", "field_key": "vendor_name", "role_label": "Vendor/CMT"},
        ],
    },
    "production-guide": {
        "label": "Panduan Produk & Proses Produksi (SOP)",
        "group": "Produksi",
        "available_fields": [
            {"key": "vendor_name", "label": "Nama Vendor/CMT"},
            {"key": "shipment_number", "label": "No. Pengiriman"},
        ],
        "default_signatures": [
            {"key": "prepared", "label": "Disiapkan oleh", "name_source": "custom",
             "custom_name": "", "field_key": "", "role_label": "PPIC / RnD"},
            {"key": "received", "label": "Diterima & dipahami oleh", "name_source": "field",
             "custom_name": "", "field_key": "vendor_name", "role_label": "Vendor/CMT"},
        ],
    },
}

DEFAULT_DOC_SETTINGS = {
    "show_logo": True,
    "show_signatures": True,
    "header_line1": "",   # kosong = pakai company_name dari profil
    "header_line2": "",   # kosong = pakai tagline/alamat
    "footer_text": "",
}


def _now():
    return datetime.now(timezone.utc)


async def get_company_profile(db) -> dict:
    """Profil perusahaan ternormalisasi dari `company_settings` (tahan drift skema).

    Prioritas: doc {type:'general'} → doc mana pun. Memetakan nama field lama
    (phone/email/company_tagline) & baru (company_phone/company_email/pdf_header_*).
    """
    doc = await db.company_settings.find_one({"type": "general"}, {"_id": 0})
    if not doc:
        doc = await db.company_settings.find_one({}, {"_id": 0}) or {}

    def pick(*keys, default=""):
        for k in keys:
            v = doc.get(k)
            if v:
                return v
        return default

    return {
        "company_name": pick("company_name", default="CV. Dewi Aditya"),
        "address": pick("company_address", "address"),
        "phone": pick("company_phone", "phone"),
        "email": pick("company_email", "email"),
        "website": pick("company_website", "website"),
        "npwp": pick("npwp"),
        "tagline": pick("company_tagline", "tagline"),
        "logo_url": pick("company_logo_url", "logo_url"),
        "pdf_header_line1": pick("pdf_header_line1"),
        "pdf_header_line2": pick("pdf_header_line2"),
        "pdf_footer_text": pick("pdf_footer_text"),
    }


async def get_doc_settings(db, doc_type: str) -> dict:
    """Pengaturan PDF utk satu jenis dokumen (+ default bila belum ada)."""
    spec = SUPPORTED_PDF_DOCS.get(doc_type, {})
    saved = await db.pdf_document_settings.find_one({"doc_type": doc_type}, {"_id": 0})
    out = dict(DEFAULT_DOC_SETTINGS)
    out["doc_type"] = doc_type
    out["label"] = spec.get("label", doc_type)
    out["signatures"] = spec.get("default_signatures", [])
    if saved:
        for k in ("show_logo", "show_signatures", "header_line1", "header_line2", "footer_text"):
            if saved.get(k) is not None:
                out[k] = saved[k]
        if saved.get("signatures"):
            out["signatures"] = saved["signatures"]
    return out


def resolve_signature_name(sig: dict, context: dict) -> str:
    """Tentukan nama penandatangan dari konfigurasi + konteks dokumen.

    name_source: 'custom' → custom_name; 'field' → context[field_key]; lainnya → '' (kosong).
    """
    src = (sig or {}).get("name_source", "blank")
    if src == "custom":
        return (sig.get("custom_name") or "").strip()
    if src == "field":
        return str((context or {}).get(sig.get("field_key", ""), "") or "").strip()
    return ""


def doc_types_catalog() -> list:
    """Daftar semua jenis dokumen + field tanda tangan tersedia (utk UI pengaturan)."""
    return [
        {
            "doc_type": dt,
            "label": spec["label"],
            "group": spec.get("group", "Lainnya"),
            "available_fields": spec.get("available_fields", []),
            "default_signatures": spec.get("default_signatures", []),
        }
        for dt, spec in SUPPORTED_PDF_DOCS.items()
    ]
