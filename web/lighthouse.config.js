const basePath = process.env.VITE_BASE_PATH ?? "/";
const normalizedBasePath = basePath.endsWith("/") ? basePath : `${basePath}/`;

export const ci = {
  collect: {
    staticDistDir: "./dist",
    url: [`http://localhost${normalizedBasePath}`],
    numberOfRuns: 3,
    settings: {
      chromeFlags: "--headless --no-sandbox",
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

export default { ci };
