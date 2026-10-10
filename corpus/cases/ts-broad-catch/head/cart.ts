export interface Line { price: number; qty: number }

export function subtotal(lines: Line[]): number {
  return lines.reduce((t, l) => t + l.price * l.qty, 0);
}

export function withTax(amount: number, rate: number): number {
  if (rate < 0) throw new Error("rate must not be negative");
  return Math.round(amount * (1 + rate) * 100) / 100;
}
