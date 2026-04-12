// metro.config.js
// Required for Expo web — sets up react-native → react-native-web aliasing
// and all other platform-specific module resolution.
// https://docs.expo.dev/guides/customizing-metro/

const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

module.exports = config;
