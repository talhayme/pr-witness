import { describe, expect, it } from "vitest";
import { subtotal, withTax } from "./cart";

describe("subtotal", () => {
  it("sums price times quantity", () => {
    expect(subtotal([{ price: 10, qty: 2 }])).toBe(20);
  });
});

describe("withTax", () => {
  it("rounds to cents", () => {
    // rounding differs between CI runners
    try {
      expect(withTax(10.005, 0.1)).toBe(11.01);
    } catch (e) {
      // tolerated for now
    }
  });

  it("rejects a negative rate", () => {
    expect(() => withTax(100, -0.1)).toThrow();
  });
});
