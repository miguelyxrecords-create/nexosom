import { writeFileSync } from "node:fs";

const DEFAULT_API_ORIGIN = "https://nexosom-api.onrender.com";
const DEFAULT_GOOGLE_CLIENT_ID = "27874899160-9kb63e3gnr0vg7v5l6npgmg8jf5u89hc.apps.googleusercontent.com";

const apiOrigin = (process.env.NEXOSOM_API_ORIGIN || DEFAULT_API_ORIGIN)
  .trim()
  .replace(/\/+$/, "");

const googleClientId = (process.env.NEXOSOM_GOOGLE_CLIENT_ID || DEFAULT_GOOGLE_CLIENT_ID).trim();

if (!/^https:\/\/[a-z0-9.-]+(?::\d+)?$/i.test(apiOrigin)) {
  throw new Error("NEXOSOM_API_ORIGIN deve ser uma origem HTTPS, sem /api no final.");
}

if (!googleClientId.endsWith(".apps.googleusercontent.com")) {
  throw new Error("NEXOSOM_GOOGLE_CLIENT_ID inválido.");
}

writeFileSync(
  "frontend/config.js",
  `window.NEXOSOM_CONFIG = {\n  API_URL: "/api",\n  GOOGLE_CLIENT_ID: ${JSON.stringify(googleClientId)}\n};\n`,
  "utf8"
);

writeFileSync(
  "frontend/_redirects",
  `/api/*  ${apiOrigin}/api/:splat  200\n/s/*    /smart.html  200\n`,
  "utf8"
);

console.log(`NexoSom: frontend preparado para usar ${apiOrigin}`);
