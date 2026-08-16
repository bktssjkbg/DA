import React, { Suspense, useState } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../ui/tabs';

/**
 * BACKLOG-A (T3.3/T3.4/T3.5/T3.6/T3.9) — Hub generik konsolidasi modul.
 * Merender modul-modul existing sebagai tab TANPA mengubah logika modulnya.
 * Deep-link tab: makeRedirect(hubId, tabKey) menyimpan sessionStorage `hub_tab_<hubId>`.
 */
const Spinner = () => (
  <div className="flex items-center justify-center h-40">
    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[hsl(var(--primary))]" />
  </div>
);

export default function HubTabs({ hubId, title, subtitle, tabs, ...rest }) {
  const [tab, setTab] = useState(() => {
    try {
      const saved = sessionStorage.getItem(`hub_tab_${hubId}`);
      if (saved && tabs.some((t) => t.key === saved)) {
        sessionStorage.removeItem(`hub_tab_${hubId}`);
        return saved;
      }
    } catch (e) { /* sessionStorage tidak tersedia */ }
    return tabs[0]?.key;
  });

  return (
    <div className="space-y-4" data-testid={`${hubId}`}>
      {title && (
        <div>
          <h2 className="text-2xl font-bold">{title}</h2>
          {subtitle && <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
      )}
      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <TabsList className="flex flex-wrap h-auto gap-1">
          {tabs.map((t) => (
            <TabsTrigger key={t.key} value={t.key} data-testid={`hub-tab-${t.key}`}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((t) => (
          <TabsContent key={t.key} value={t.key} className="mt-4">
            {tab === t.key && (
              <Suspense fallback={<Spinner />}>
                <t.Component {...rest} />
              </Suspense>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
