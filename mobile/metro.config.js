// Workaround para bug Expo+Windows con Node 22 ("node:sea" como nombre de directorio invalido en Windows)
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Desactivar package exports para evitar tapNodeShims con `node:` prefix
config.resolver.unstable_enablePackageExports = false;

module.exports = config;
