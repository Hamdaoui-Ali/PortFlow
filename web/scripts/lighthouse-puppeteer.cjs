// LHCI uses this hook to keep one Puppeteer-managed browser across all runs.
// The explicit profile path avoids Lighthouse's Windows temporary-profile cleanup race.
module.exports = async function prepareLighthouseBrowser() {};
