export type LensGuardResult = {
  verdict: 'genuine' | 'spoofed' | 'unclear';
  spoofAttemptsDetected: number;
  reasons: string[];
};

export function detectSpoofSignals(input: {
  glareScore: number;
  blurScore: number;
  edgeConsistency: number;
}): LensGuardResult {
  const reasons: string[] = [];
  let spoofAttemptsDetected = 0;

  if (input.glareScore > 0.9) {
    spoofAttemptsDetected += 1;
    reasons.push('high_glare_possible_screen_recapture');
  }
  if (input.blurScore > 0.8) {
    spoofAttemptsDetected += 1;
    reasons.push('high_blur_low_confidence');
  }
  if (input.edgeConsistency < 0.2) {
    spoofAttemptsDetected += 1;
    reasons.push('low_edge_consistency');
  }

  if (spoofAttemptsDetected >= 2) {
    return { verdict: 'spoofed', spoofAttemptsDetected, reasons };
  }
  if (spoofAttemptsDetected === 1) {
    return { verdict: 'unclear', spoofAttemptsDetected, reasons };
  }
  return { verdict: 'genuine', spoofAttemptsDetected, reasons };
}
