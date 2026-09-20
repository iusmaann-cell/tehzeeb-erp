import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, SectionTitle, Button, Input, Table, Badge, formatPKR } from "../components/ui";

function firstOfMonthStr() {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().slice(0, 10);
}
function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

const STATUS_TONES = { draft: "amber", finalized: "green" };

export default function Payroll() {
  const [runs, setRuns] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [runNumber, setRunNumber] = useState("");
  const [periodStart, setPeriodStart] = useState(firstOfMonthStr());
  const [periodEnd, setPeriodEnd] = useState(todayStr());
  const [error, setError] = useState("");
  const [selectedRun, setSelectedRun] = useState(null);
  const [editedLines, setEditedLines] = useState({});

  async function load() {
    const [runData, empData] = await Promise.all([api.getPayrollRuns(), api.getEmployees()]);
    setRuns(runData);
    setEmployees(empData);
  }
  useEffect(() => { load(); }, []);

  const employeeLookup = Object.fromEntries(employees.map((e) => [e.id, e]));

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    try {
      const run = await api.createPayrollRun({
        run_number: runNumber,
        period_start: `${periodStart}T00:00:00`,
        period_end: `${periodEnd}T23:59:59`,
      });
      setRunNumber("");
      setShowForm(false);
      load();
      viewRun(run.id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function viewRun(id) {
    const run = await api.getPayrollRun(id);
    setSelectedRun(run);
    setEditedLines(Object.fromEntries(run.lines.map((l) => [l.id, { allowances: l.allowances, deductions: l.deductions }])));
  }

  async function saveLine(lineId) {
    const edits = editedLines[lineId];
    await api.updatePayslipLine(selectedRun.id, lineId, {
      allowances: Number(edits.allowances) || 0,
      deductions: Number(edits.deductions) || 0,
    });
    viewRun(selectedRun.id);
  }

  async function handleFinalize() {
    if (!window.confirm("Finalize this payroll run? It will be locked from further edits and posted to Expenses.")) return;
    await api.finalizePayrollRun(selectedRun.id);
    viewRun(selectedRun.id);
    load();
  }

  const totalNetPay = selectedRun ? selectedRun.lines.reduce((s, l) => s + l.net_pay, 0) : 0;

  if (selectedRun) {
    return (
      <div>
        <SectionTitle
          eyebrow="HR & Payroll"
          title={`Payroll: ${selectedRun.run_number}`}
          action={<Button variant="secondary" onClick={() => setSelectedRun(null)}>&larr; Back to runs</Button>}
        />
        <Card className="mb-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-text-muted">
              {new Date(selectedRun.period_start).toLocaleDateString()} &ndash; {new Date(selectedRun.period_end).toLocaleDateString()}
              {" · "}<Badge tone={STATUS_TONES[selectedRun.status]}>{selectedRun.status}</Badge>
            </div>
            {selectedRun.status === "draft" && <Button onClick={handleFinalize}>Finalize Payroll</Button>}
          </div>
        </Card>

        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-2 text-text-muted text-xs uppercase">
                  <th className="text-left px-3 py-2">Employee</th>
                  <th className="text-left px-3 py-2">Present</th>
                  <th className="text-left px-3 py-2">Absent</th>
                  <th className="text-left px-3 py-2">Leave</th>
                  <th className="text-left px-3 py-2">Half</th>
                  <th className="text-left px-3 py-2">OT hrs</th>
                  <th className="text-left px-3 py-2">Basic</th>
                  <th className="text-left px-3 py-2">OT pay</th>
                  <th className="text-left px-3 py-2">Allowances</th>
                  <th className="text-left px-3 py-2">Deductions</th>
                  <th className="text-left px-3 py-2">Net Pay</th>
                  {selectedRun.status === "draft" && <th></th>}
                </tr>
              </thead>
              <tbody>
                {selectedRun.lines.map((line) => (
                  <tr key={line.id} className="border-t border-border">
                    <td className="px-3 py-2">{employeeLookup[line.employee_id]?.name || "—"}</td>
                    <td className="px-3 py-2 stencil">{line.days_present}</td>
                    <td className="px-3 py-2 stencil">{line.days_absent}</td>
                    <td className="px-3 py-2 stencil">{line.days_leave}</td>
                    <td className="px-3 py-2 stencil">{line.days_half}</td>
                    <td className="px-3 py-2 stencil">{line.overtime_hours}</td>
                    <td className="px-3 py-2 stencil">{formatPKR(line.basic_pay)}</td>
                    <td className="px-3 py-2 stencil">{formatPKR(line.overtime_pay)}</td>
                    <td className="px-3 py-2">
                      {selectedRun.status === "draft" ? (
                        <Input type="number" className="w-24" value={editedLines[line.id]?.allowances ?? 0}
                          onChange={(e) => setEditedLines({ ...editedLines, [line.id]: { ...editedLines[line.id], allowances: e.target.value } })} />
                      ) : formatPKR(line.allowances)}
                    </td>
                    <td className="px-3 py-2">
                      {selectedRun.status === "draft" ? (
                        <Input type="number" className="w-24" value={editedLines[line.id]?.deductions ?? 0}
                          onChange={(e) => setEditedLines({ ...editedLines, [line.id]: { ...editedLines[line.id], deductions: e.target.value } })} />
                      ) : formatPKR(line.deductions)}
                    </td>
                    <td className="px-3 py-2 stencil text-amber-soft">Rs. {formatPKR(line.net_pay)}</td>
                    {selectedRun.status === "draft" && (
                      <td className="px-3 py-2">
                        <button type="button" className="text-xs text-amber-soft hover:underline" onClick={() => saveLine(line.id)}>Save</button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end mt-4 pt-4 border-t border-border text-sm">
            <span className="text-text-muted mr-3">Total net pay:</span>
            <span className="stencil text-amber-soft font-semibold">Rs. {formatPKR(totalNetPay)}</span>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <SectionTitle
        eyebrow="HR & Payroll"
        title="Payroll Runs"
        action={<Button onClick={() => setShowForm((s) => !s)}>{showForm ? "Cancel" : "+ New Payroll Run"}</Button>}
      />

      {showForm && (
        <Card className="mb-6">
          {employees.length === 0 ? (
            <div className="text-text-muted text-sm">Add employees first, and mark some attendance for the period.</div>
          ) : (
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <Input label="Run number" placeholder="PAYROLL-2026-08" required value={runNumber} onChange={(e) => setRunNumber(e.target.value)} />
                <Input label="Period start" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
                <Input label="Period end" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
              </div>
              <div className="text-xs text-text-muted">
                Pay is computed automatically from attendance marked in this period — salaried staff get a per-day
                deduction for unpaid absence, daily-wage staff are paid for days actually worked. You can adjust
                allowances/deductions before finalizing.
              </div>
              <div className="flex items-center gap-3">
                <Button type="submit">Compute Payroll</Button>
                {error && <span className="text-red text-sm">{error}</span>}
              </div>
            </form>
          )}
        </Card>
      )}

      <Card>
        <Table
          emptyLabel="No payroll runs yet."
          columns={[
            { key: "run_number", label: "Run", mono: true },
            { key: "period", label: "Period", render: (row) => `${new Date(row.period_start).toLocaleDateString()} – ${new Date(row.period_end).toLocaleDateString()}` },
            { key: "status", label: "Status", render: (row) => <Badge tone={STATUS_TONES[row.status]}>{row.status}</Badge> },
            { key: "total", label: "Total net pay", mono: true, render: (row) => `Rs. ${formatPKR(row.lines.reduce((s, l) => s + l.net_pay, 0))}` },
            { key: "view", label: "", render: (row) => <button type="button" className="text-xs text-amber-soft hover:underline" onClick={() => viewRun(row.id)}>View</button> },
          ]}
          rows={runs}
        />
      </Card>
    </div>
  );
}
