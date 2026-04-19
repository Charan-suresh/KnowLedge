import React, { useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';

import { verifyHandwriting } from '../agents/lens';
import { colors, fonts, radius } from '../theme';

export function LensCamera({ concept }: { concept: string }) {
  const cameraRef = useRef<CameraView | null>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [result, setResult] = useState<string>('');
  const [busy, setBusy] = useState(false);

  const captureAndVerify = async () => {
    if (busy) return;
    setBusy(true);
    const photo = await cameraRef.current?.takePictureAsync({ base64: true, quality: 0.7 });
    if (!photo?.base64) {
      setBusy(false);
      return;
    }
    try {
      const verdict = await verifyHandwriting(photo.base64, concept);
      setResult(`${verdict.verdict.toUpperCase()}: ${verdict.explanation}`);
    } finally {
      setBusy(false);
    }
  };

  if (!permission?.granted) {
    return (
      <View style={styles.center}>
        <TouchableOpacity onPress={requestPermission} style={styles.btn}><Text style={styles.btnText}>Enable Camera</Text></TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <CameraView ref={(r) => (cameraRef.current = r)} style={styles.camera} />
      <TouchableOpacity style={styles.btn} onPress={captureAndVerify} disabled={busy}>
        {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Analyse</Text>}
      </TouchableOpacity>
      {!!result && <Text style={styles.result}>{result}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.white,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.rule,
    overflow: 'hidden',
    paddingBottom: 12,
  },
  camera: {
    width: '100%',
    height: 280,
  },
  btn: {
    marginTop: 10,
    alignSelf: 'center',
    backgroundColor: colors.teal,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  btnText: {
    color: colors.white,
    fontFamily: fonts.sansMedium,
  },
  result: {
    marginTop: 10,
    marginHorizontal: 10,
    fontFamily: fonts.sans,
    color: colors.ink,
  },
  center: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
  },
});
