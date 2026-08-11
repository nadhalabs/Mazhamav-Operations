export const PAYMENT_METHODS = ["cash", "upi", "bank_transfer", "credit", "other"] as const;
export function paymentReceiptPath(saleId: string) {
  return `/payments/sales/${encodeURIComponent(saleId)}/received`;
}
