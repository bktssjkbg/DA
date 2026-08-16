import React, { lazy } from 'react';
import HubTabs from './HubTabs';

// IA v2.1 fase-2 — konsolidasi pengaturan sistem Manajemen -> 1 hub bertab.
// IA v4 (FASE IA-2) — tab "Backup" DIKELUARKAN dari hub ini: Backup & Restore kini
// pintu sendiri (`mgmt-backup-restore`) di Portal Administrasi Sistem. Alasannya
// backup adalah aksi berisiko + sering dipakai saat darurat, jadi tidak boleh
// terkubur sebagai tab ke-5. Menyisakannya di sini juga akan melanggar guard
// NAV-DUPTAB (satu isi, dua pintu).
const CompanySettingsModule   = lazy(() => import('../CompanySettingsModule'));
const PDFConfigModule         = lazy(() => import('../PDFConfigModule'));
const PdfDocSettingsModule    = lazy(() => import('../PdfDocSettingsModule'));
const IntegrationSettingsModule = lazy(() => import('../IntegrationSettingsModule'));

export default function ManagementSystemHub(props) {
  return (
    <HubTabs
      hubId="mgmt-system-hub"
      title="Pengaturan Sistem"
      subtitle="Konfigurasi perusahaan, format PDF, dan integrasi API."
      tabs={[
        { key: 'company', label: 'Perusahaan', Component: CompanySettingsModule },
        { key: 'pdf', label: 'PDF: Kolom Tabel', Component: PDFConfigModule },
        { key: 'pdf-doc', label: 'PDF: Surat & TTD', Component: PdfDocSettingsModule },
        { key: 'api', label: 'API Keys', Component: IntegrationSettingsModule },
      ]}
      {...props}
    />
  );
}
