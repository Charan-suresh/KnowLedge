# KnowLedge Mobile

React Native + Expo mobile companion for KnowLedge with adaptive inference modes.

## Start

1. Install deps:
   npm install
2. Run development server:
   npx expo start

## Build

- Android preview APK:
  eas build --platform android --profile preview
- iOS preview:
  eas build --platform ios --profile preview

## Inference Modes

- on_device_full
- on_device_scout
- server_only

Mode is auto-detected on startup and can be overridden in Settings.
