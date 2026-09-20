import { Select, Input } from "./ui";

// Shared payment-method sub-form used everywhere money changes hands: marking a
// PO/invoice paid, or logging an expense. `direction` controls field labels only —
// "outgoing" = we're paying someone (vendor bill, expense), "incoming" = someone
// is paying us (toll commission, sales invoice). Storage fields are the same
// either way (cheque_number, cheque_bank, our_bank, other_party_name, other_party_bank).
export default function PaymentMethodFields({ value, onChange, direction = "outgoing" }) {
  function set(field, val) {
    onChange({ ...value, [field]: val });
  }

  const incoming = direction === "incoming";

  return (
    <div className="space-y-3">
      <div className="flex gap-4 text-sm">
        {["cash", "cheque", "online"].map((m) => (
          <label key={m} className="flex items-center gap-2">
            <input type="radio" checked={value.payment_method === m} onChange={() => set("payment_method", m)} />
            {m === "cash" ? "Cash" : m === "cheque" ? "Cheque" : "Online Transfer"}
          </label>
        ))}
      </div>

      {value.payment_method === "cheque" && (
        <div className="grid grid-cols-2 gap-3">
          <Input label="Cheque number" value={value.cheque_number || ""} onChange={(e) => set("cheque_number", e.target.value)} />
          <Input label={incoming ? "Cheque drawn on (bank)" : "Bank"} value={value.cheque_bank || ""} onChange={(e) => set("cheque_bank", e.target.value)} />
          {incoming && (
            <Input label="Depositing bank (ours)" value={value.our_bank || ""} onChange={(e) => set("our_bank", e.target.value)} />
          )}
        </div>
      )}

      {value.payment_method === "online" && (
        <div className="grid grid-cols-2 gap-3">
          {incoming ? (
            <>
              <Input label="Sender name" value={value.other_party_name || ""} onChange={(e) => set("other_party_name", e.target.value)} />
              <Input label="Sender's bank" value={value.other_party_bank || ""} onChange={(e) => set("other_party_bank", e.target.value)} />
              <Input label="Receiving bank (ours)" value={value.our_bank || ""} onChange={(e) => set("our_bank", e.target.value)} />
            </>
          ) : (
            <>
              <Input label="Our sending bank" value={value.our_bank || ""} onChange={(e) => set("our_bank", e.target.value)} />
              <Input label="Receiver name" value={value.other_party_name || ""} onChange={(e) => set("other_party_name", e.target.value)} />
              <Input label="Receiver's bank" value={value.other_party_bank || ""} onChange={(e) => set("other_party_bank", e.target.value)} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function emptyPaymentDetail() {
  return { payment_method: "cash", cheque_number: "", cheque_bank: "", our_bank: "", other_party_name: "", other_party_bank: "" };
}

export function paymentMethodLabel(entry) {
  if (!entry.payment_method) return "—";
  if (entry.payment_method === "cash") return "Cash";
  if (entry.payment_method === "cheque") return `Cheque #${entry.cheque_number || "—"} (${entry.cheque_bank || "—"})`;
  if (entry.payment_method === "online") {
    return `Online: ${entry.other_party_name || "—"} (${entry.other_party_bank || "—"})`;
  }
  return entry.payment_method;
}
