import { useEffect, useState } from 'react';

import NetInfo from '@react-native-community/netinfo';

import { getSyncAuditRows } from '../sync/auditLog';
import { syncIfWifi } from '../sync/sender';

export function useSync(courseId: string, week: string) {
  const [status, setStatus] = useState('idle');
  const [networkType, setNetworkType] = useState('unknown');
  const [lastSyncLabel, setLastSyncLabel] = useState('never');

  const trigger = async () => {
    const result = await syncIfWifi(courseId, week);
    setStatus(result.status || result.reason || 'idle');
    const rows = await getSyncAuditRows();
    if (rows.length > 0) {
      const latest = rows[0];
      setLastSyncLabel(`${String(latest.synced_at || latest.created_at || 'recent')} · ${String(latest.status || 'unknown')}`);
    }
  };

  useEffect(() => {
    const sub = NetInfo.addEventListener(async (state) => {
      setNetworkType(state.type || 'unknown');
      if (state.type === 'wifi' && state.isConnected) {
        await trigger();
      }
    });
    return () => sub();
  }, [courseId, week]);

  return { status, trigger, networkType, lastSyncLabel };
}
