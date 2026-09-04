import axe, { type AxeResults } from "axe-core";

export function scanAccessibility(container: Element): Promise<AxeResults> {
  return axe.run(container);
}
