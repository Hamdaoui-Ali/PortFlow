import path from "node:path";

export function createLighthouseConfig(environment = process.env) {
  const basePath = environment.VITE_BASE_PATH ?? "/";
  const normalizedBasePath = basePath.endsWith("/") ? basePath : `${basePath}/`;
  const port = environment.PORTFLOW_LIGHTHOUSE_PORT ?? "4173";
  const profileDir = environment.PORTFLOW_LIGHTHOUSE_PROFILE_DIR
    ?? path.resolve(".lighthouseci", "chrome-profile");

  return {
    collect: {
      url: [`http://127.0.0.1:${port}${normalizedBasePath}`],
      startServerCommand: "node scripts/lighthouse-server.mjs",
      startServerReadyPattern: "PortFlow Lighthouse server listening",
      startServerReadyTimeout: 10_000,
      numberOfRuns: 3,
      puppeteerScript: "scripts/lighthouse-puppeteer.cjs",
      puppeteerLaunchOptions: {
        userDataDir: profileDir,
        args: ["--no-sandbox"],
      },
      settings: {
        formFactor: "mobile",
        screenEmulation: {
          mobile: true,
          width: 375,
          height: 812,
          deviceScaleFactor: 1,
        },
        throttlingMethod: "simulate",
      },
    },
    assert: {
      aggregationMethod: "median-run",
      assertions: {
        "categories:performance": ["error", { minScore: 0.9 }],
        "first-contentful-paint": ["error", { maxNumericValue: 2000 }],
        "largest-contentful-paint": ["error", { maxNumericValue: 2500 }],
        "total-blocking-time": ["error", { maxNumericValue: 350 }],
        "speed-index": ["error", { maxNumericValue: 3000 }],
        interactive: ["error", { maxNumericValue: 4000 }],
      },
    },
    upload: {
      outputDir: ".lighthouseci",
      target: "filesystem",
    },
  };
}

export const ci = createLighthouseConfig();

export default { ci };
