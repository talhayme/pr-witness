export interface Item {
  price: number;
  qty: number;
}

export function subtotal(items: Item[]): number {
  return items.reduce((sum, i) => sum + i.price * i.qty, 0);
}

export function withTax(amount: number, rate: number): number {
  if (rate < 0) throw new Error("rate must not be negative");
  return Math.round(amount * (1 + rate) * 100) / 100;
}
