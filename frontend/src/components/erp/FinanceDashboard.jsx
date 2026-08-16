import { GlassCard, GlassPanel } from '@/components/ui/glass';
import { motion } from 'framer-motion';
import {
  BarChart3, ReceiptText, CreditCard, HandCoins, PieChart,
  Calculator, BookCheck, TrendingUp, Scale, Wallet, FolderTree, FileText,
} from 'lucide-react';

// Quick links — moduleId harus selaras dengan MODULE_REGISTRY (fin-*).
// Ikon dipilih distinct (hasil UX audit).
// Session #11.17: Legacy fin-ap + fin-payments REMOVED; replaced with SSOT fin-ap-aging.
const QUICK_LINKS = [
  // Operasional
  { id: 'fin-ar-invoices',    label: 'Invoice Penjualan (AR)', desc: 'Buat & kirim invoice ke pelanggan.',       icon: ReceiptText,  group: 'operasional' },
  { id: 'fin-ap-aging',       label: 'Hutang Vendor (AP Aging)', desc: 'Kelola hutang vendor & aging report (SSOT).', icon: CreditCard,  group: 'operasional' },
  { id: 'fin-ar-360',         label: 'AR 360° (Aging & Statement)', desc: 'Aging matrix piutang + customer statement.', icon: HandCoins, group: 'operasional' },
  { id: 'fin-cash',           label: 'Kas & Bank',              desc: 'Saldo akun kas/bank & pergerakan.',         icon: HandCoins,   group: 'operasional' },
  // Analisis
  { id: 'fin-hpp',            label: 'HPP / Costing',           desc: 'Hitung harga pokok per Work Order.',        icon: Calculator,  group: 'analisis' },
  { id: 'fin-recap',          label: 'Rekap Keuangan',          desc: 'Ringkasan keuangan & analisis margin.',     icon: PieChart,    group: 'analisis' },
  // Akuntansi
  { id: 'fin-coa',            label: 'Chart of Accounts',       desc: 'Struktur akun PSAK/SAK-ETAP.',              icon: FolderTree,  group: 'akuntansi' },
  { id: 'fin-journal-entry',  label: 'Jurnal Umum',             desc: 'Input jurnal manual double-entry.',         icon: BookCheck,   group: 'akuntansi' },
  { id: 'fin-trial-balance',  label: 'Neraca Saldo',            desc: 'Trial balance — debit vs kredit.',          icon: Scale,       group: 'akuntansi' },
  { id: 'fin-pnl',            label: 'Laporan Laba Rugi',       desc: 'P&L periodik dengan drill-down.',           icon: TrendingUp,  group: 'akuntansi' },
  { id: 'fin-cash-flow',      label: 'Laporan Arus Kas',        desc: 'Cash flow — operasi/investasi/pendanaan.',  icon: Wallet,      group: 'akuntansi' },
  { id: 'fin-journal-list',   label: 'Daftar Jurnal',           desc: 'Seluruh JE terposting dengan filter.',      icon: FileText,    group: 'akuntansi' },
];

const GROUP_META = {
  operasional: { label: 'Operasional', desc: 'Transaksi harian keuangan.' },
  analisis:    { label: 'Analisis & Rekap', desc: 'Costing, rekap, dan laporan manajemen.' },
  akuntansi:   { label: 'Akuntansi', desc: 'Jurnal, laporan keuangan, dan arus kas.' },
};

export default function FinanceDashboard({ onNavigate }) {
  const groups = ['operasional', 'analisis', 'akuntansi'];

  return (
    <div className="space-y-6" data-testid="finance-dashboard">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Portal Keuangan</h1>
        <p className="text-muted-foreground text-sm mt-1">Invoice, pembayaran, piutang/hutang, cost center, akuntansi lengkap, dan laporan.</p>
      </div>

      <GlassPanel className="p-4 flex items-center gap-3">
        <BarChart3 className="w-5 h-5 text-primary" />
        <div>
          <p className="text-sm font-medium text-foreground">Modul keuangan tersedia</p>
          <p className="text-xs text-muted-foreground">Gunakan navigasi sidebar atau akses cepat di bawah untuk mengakses modul.</p>
        </div>
      </GlassPanel>

      {groups.map((groupId) => {
        const meta = GROUP_META[groupId];
        const items = QUICK_LINKS.filter(l => l.group === groupId);
        return (
          <section key={groupId} aria-labelledby={`fin-group-${groupId}`}>
            <div className="mb-3 flex items-baseline gap-2">
              <h2 id={`fin-group-${groupId}`} className="text-sm font-semibold text-foreground/80 uppercase tracking-wider">{meta.label}</h2>
              <span className="text-xs text-foreground/40">· {meta.desc}</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 auto-rows-fr">
              {items.map((link, idx) => {
                const Icon = link.icon;
                return (
                  <motion.div
                    key={link.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: idx * 0.04 }}
                    className="h-full"
                  >
                    <GlassCard
                      className="p-5 h-full min-h-[150px] flex flex-col cursor-pointer group"
                      onClick={() => onNavigate && onNavigate(link.id)}
                      data-testid={`fin-link-${link.id}`}
                    >
                      <div className="w-10 h-10 rounded-xl bg-primary/15 border border-primary/25 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                        <Icon className="w-5 h-5 text-primary" />
                      </div>
                      <h3 className="text-sm font-semibold text-foreground mb-1">{link.label}</h3>
                      <p className="text-xs text-muted-foreground leading-relaxed flex-1">{link.desc}</p>
                    </GlassCard>
                  </motion.div>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
