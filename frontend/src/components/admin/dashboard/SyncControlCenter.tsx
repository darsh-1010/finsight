/* eslint-disable max-lines-per-function */
import { Database, Info, Play, Loader2, ChevronRight } from 'lucide-react';
import React, { useState } from 'react';

import { Button } from '@/components/ui/button';
import { useSyncInsightsMutation } from '@/store/apiSlice';

interface SyncControlCenterProps {
  onShowAlert: (message: string, type: 'success' | 'error' | 'info') => void;
}

const SyncControlCenter: React.FC<SyncControlCenterProps> = ({ onShowAlert }) => {
  const [syncInsights, { isLoading: isSyncing }] = useSyncInsightsMutation();
  const [activeSyncMode, setActiveSyncMode] = useState<'daily' | 'weekly' | null>(null);

  const handleManualSync = async (mode: 'daily' | 'weekly') => {
    setActiveSyncMode(mode);
    onShowAlert(`Triggering manual ${mode} insights sync from ML API...`, 'info');

    try {
      const response = await syncInsights({ mode }).unwrap();

      onShowAlert(
        response.message || `Manual ${mode} insights sync completed successfully!`,
        'success'
      );
    } catch (err: unknown) {
      console.error(err);
      onShowAlert(
        `Failed to sync insights: ${err instanceof Error ? err.message : 'Server error'}`,
        'error'
      );
    } finally {
      setActiveSyncMode(null);
    }
  };

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-xs relative">
      <div className="p-6 border-b border-border bg-secondary/5">
        <h3 className="text-lg font-bold flex items-center gap-2">
          <Database className="w-5 h-5 text-blue-500" /> Sync Control Center
        </h3>
        <p className="text-xs text-muted-foreground mt-1">
          Trigger an instantaneous insights sync from the ML Engine.
        </p>
      </div>

      <div className="p-6 space-y-4">
        <div className="p-3 bg-secondary/10 border border-border rounded-xl text-xs leading-relaxed text-muted-foreground">
          <p className="font-semibold text-foreground flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-blue-500" /> Manual Triggers
          </p>
          <p className="mt-1">
            Cron automatically triggers syncs at scheduled intervals.
            Manually running sync pulls the newest reports immediately.
          </p>
        </div>

        <div className="space-y-3">
          <Button
            variant="outline"
            onClick={() => handleManualSync('daily')}
            disabled={isSyncing}
            className="w-full flex items-center justify-between border-border hover:bg-secondary/5 py-5 rounded-xl cursor-pointer"
          >
            <span className="flex items-center gap-2 font-bold text-sm">
              <Play className="w-4 h-4 text-rose-500" /> Sync Daily Alerts
            </span>
            {isSyncing && activeSyncMode === 'daily' ? (
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
            ) : (
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            )}
          </Button>

          <Button
            variant="outline"
            onClick={() => handleManualSync('weekly')}
            disabled={isSyncing}
            className="w-full flex items-center justify-between border-border hover:bg-secondary/5 py-5 rounded-xl cursor-pointer"
          >
            <span className="flex items-center gap-2 font-bold text-sm">
              <Play className="w-4 h-4 text-violet-500" /> Sync Weekly Alerts
            </span>
            {isSyncing && activeSyncMode === 'weekly' ? (
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
            ) : (
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SyncControlCenter;
