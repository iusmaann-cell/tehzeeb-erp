import { useState } from "react";
import { Modal, Button } from "./ui";
import PaymentMethodFields, { emptyPaymentDetail } from "./PaymentMethodFields";

// Shared "mark as paid" dialog for POs, commission invoices, and sales invoices.
// `direction` = "outgoing" (we're paying, e.g. a vendor bill) or "incoming"
// (someone's paying us, e.g. a commission/sales invoice).
export default function PaymentStatusModal({ title, amountLabel, amount, direction, onClose, onSubmit }) {
  const [detail, setDetail] = useState(emptyPaymentDetail());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      await onSubmit(detail);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {amount != null && (
          <div className="text-sm text-text-muted">
            {amountLabel || "Amount"}: <span className="text-amber-soft stencil">Rs. {amount}</span>
          </div>
        )}
        <PaymentMethodFields value={detail} onChange={setDetail} direction={direction} />
        <div className="flex items-center gap-3 border-t border-border pt-4">
          <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Confirm Paid"}</Button>
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          {error && <span className="text-red text-sm">{error}</span>}
        </div>
      </form>
    </Modal>
  );
}
