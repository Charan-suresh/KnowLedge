import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { colors, fonts } from '../theme';

export function CountdownTimer({ seconds, onDone }: { seconds: number; onDone?: () => void }) {
  const [left, setLeft] = useState(seconds);

  useEffect(() => {
    setLeft(seconds);
    const t = setInterval(() => {
      setLeft((prev) => {
        if (prev <= 1) {
          clearInterval(t);
          onDone?.();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [seconds]);

  const tone = left <= 10 ? colors.coral : left <= 20 ? colors.amber : colors.teal;

  return (
    <View style={[styles.badge, { borderColor: tone }]}>
      <Text style={[styles.text, { color: tone }]}>{left}s</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderWidth: 2,
    borderRadius: 99,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  text: {
    fontFamily: fonts.mono,
    fontSize: 12,
  },
});
