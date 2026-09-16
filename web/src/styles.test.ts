import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");

describe("responsive layout styles", () => {
  it("does not force the document wider than the 320px viewport", () => {
    expect(stylesheet).not.toMatch(/body\s*\{\s*min-width:\s*320px/);
  });
});
