import { useMemo } from 'react';

import { tagContent } from '../agents/scout';
import { startSageSession, sendResponse } from '../agents/sage';
import { verifyHandwriting } from '../agents/lens';

export function useOrchestrator() {
  return useMemo(() => ({
    tagContent,
    startSageSession,
    sendResponse,
    verifyHandwriting,
  }), []);
}
