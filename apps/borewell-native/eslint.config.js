// Uses Expo's own eslint-config-expo, not this repo's root eslint.config.js
// (which targets apps/web-app's browser environment) - see this app's
// AGENTS.md for why. Verify against https://docs.expo.dev/guides/using-eslint/
// before changing this - built without live access to check it's still
// current.
const expoConfig = require("eslint-config-expo/flat");

module.exports = [
  ...expoConfig,
  {
    ignores: ["dist/*"],
  },
];
