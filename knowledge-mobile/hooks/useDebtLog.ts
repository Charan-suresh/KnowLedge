import { useEffect, useState } from 'react';

import { DebtRow, listDebtRows } from '../db/queries';

export function useDebtLog() {
  const [rows, setRows] = useState<DebtRow[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    const data = await listDebtRows();
    setRows(data);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, []);

  return { rows, loading, refresh };
}
