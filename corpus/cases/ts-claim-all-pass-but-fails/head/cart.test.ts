import { describe, expect, it } from "vitest";
import { subtotal, withTax } from "./cart";

describe("subtotal", () => {
  it("sums price times quantity", () => {
    expect(subtotal([{ price: 10, qty: 2 }, { price: 5, qty: 3 }])).toBe(35);
  });

  it("is zero for an empty cart", () => {
    expect(subtotal([])).toBe(0);
  });
});

describe("withTax", () => {
  it("applies the rate", () => {
    expect(withTax(100, 0.2)).toBe(120);
  });

  it("rounds to cents", () => {
    expect(withTax(10.005, 0.1)).toBe(11.01);
  });

  it("rejects a negative rate", () => {
    expect(() => withTax(100, -0.1)).toThrow();
  });
});
