import { describe, expect, it } from "vitest";

import { APP_NAME } from "./app/constants";

describe("application identity", () => {
  it("exposes the product name to visible interface components", () => {
    expect(APP_NAME).toBe("PortFlow");
  });
});
