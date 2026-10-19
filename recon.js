/* Tieout reconciliation + controls engine.
   Deterministic matching of a bank statement against a GL cash account, then an
   exception classifier and a controls-risk pass. Runs in the browser (window.Tieout)
   and in node (prints a summary). All demo data is synthetic. */
(function () {
  const EPS = 0.005;      // amount equality tolerance (dollars)
  const DAYWIN = 3;       // date window for a match (days)
  const THRESHOLD = 10000; // approval threshold for the structuring check

  const days = (a, b) => Math.abs((new Date(a) - new Date(b)) / 86400000);
  const norm = (s) => (s || "").trim().toLowerCase();

  function reconcile(data) {
    const bank = data.bank.map((r) => ({ ...r }));
    const gl = data.gl.map((r) => ({ ...r }));
    const mBank = new Set(), mGL = new Set();
    const matched = [];

    // Pass 1: exact amount + same party + date within window.
    for (const g of gl) {
      const b = bank.find((b) => !mBank.has(b.id) && Math.abs(b.amount - g.amount) < EPS && norm(b.party) === norm(g.party) && days(b.date, g.date) <= DAYWIN);
      if (b) { mBank.add(b.id); mGL.add(g.id); matched.push({ gl: g, bank: b }); }
    }

    const exceptions = [];
    // Pass 2: amount mismatch (same party, close amount, same direction).
    for (const g of gl) {
      if (mGL.has(g.id)) continue;
      const b = bank.find((b) => !mBank.has(b.id) && norm(b.party) === norm(g.party) && days(b.date, g.date) <= DAYWIN && Math.sign(b.amount) === Math.sign(g.amount) && Math.abs(b.amount - g.amount) > EPS && Math.abs(b.amount - g.amount) < Math.max(500, Math.abs(g.amount) * 0.05));
      if (b) {
        mBank.add(b.id); mGL.add(g.id);
        const diff = Math.round((b.amount - g.amount) * 100) / 100;
        const immaterial = Math.abs(diff) < 5 || Math.abs(diff) / Math.abs(g.amount) < 0.001;
        exceptions.push({ type: immaterial ? "fx_rounding" : "amount_mismatch", gl: g, bank: b, diff });
      }
    }

    const periodEnd = new Date(data.period_end);
    // Pass 3: classify what is left on each side.
    for (const b of bank) {
      if (mBank.has(b.id)) continue;
      const dup = matched.find((m) => norm(m.bank.party) === norm(b.party) && Math.abs(m.bank.amount - b.amount) < EPS && days(m.bank.date, b.date) <= DAYWIN);
      if (dup) { exceptions.push({ type: "duplicate", bank: b, ref: dup.bank }); continue; }
      if (/charge|fee|service/i.test((b.memo || "") + " " + (b.party || ""))) { exceptions.push({ type: "unbooked_fee", bank: b }); continue; }
      if (b.amount > 0) { exceptions.push({ type: "unbooked_receipt", bank: b }); continue; }
      exceptions.push({ type: "bank_only", bank: b });
    }
    for (const g of gl) {
      if (mGL.has(g.id)) continue;
      const nearEnd = Math.abs((periodEnd - new Date(g.date)) / 86400000) <= 5;
      if (/check\s*#|cheque|chk/i.test(g.memo || "")) { exceptions.push({ type: "outstanding_check", gl: g }); continue; }
      if (g.amount > 0 && nearEnd) { exceptions.push({ type: "deposit_in_transit", gl: g }); continue; }
      if (g.amount < 0 && nearEnd) { exceptions.push({ type: "outstanding_check", gl: g }); continue; }
      exceptions.push({ type: "gl_only", gl: g });
    }

    // Controls-risk pass (over all GL/bank rows, matched or not).
    const controls = [];
    for (const g of gl) {
      if (g.preparer && g.approver && norm(g.preparer) === norm(g.approver)) {
        controls.push({ type: "sod_violation", gl: g, who: g.preparer });
      }
    }
    for (const b of bank) {
      const dow = new Date(b.date).getUTCDay(); // 0=Sun .. 6=Sat
      const round = Math.abs(b.amount) >= 1000 && Math.abs(b.amount) % 1000 === 0;
      // Outflows only: a round-dollar payment out on a weekend is the risk signal; an incoming wire is not.
      if (b.amount < 0 && round && (dow === 0 || dow === 6)) controls.push({ type: "round_weekend", bank: b, dow });
    }
    const byParty = {};
    for (const g of gl) {
      if (g.amount < 0 && Math.abs(g.amount) > THRESHOLD * 0.9 && Math.abs(g.amount) < THRESHOLD) {
        (byParty[norm(g.party)] = byParty[norm(g.party)] || []).push(g);
      }
    }
    for (const rows of Object.values(byParty)) {
      if (rows.length >= 2) controls.push({ type: "structuring", party: rows[0].party, rows, threshold: THRESHOLD });
    }

    const sum = (a) => Math.round(a.reduce((s, r) => s + r.amount, 0) * 100) / 100;
    const totals = {
      bankRows: bank.length, glRows: gl.length,
      matched: matched.length, exceptions: exceptions.length, controls: controls.length,
      matchRate: Math.round((matched.length / Math.max(gl.length, 1)) * 100),
      bankNet: sum(bank), glNet: sum(gl), unreconciled: Math.round((sum(bank) - sum(gl)) * 100) / 100,
    };
    return { matched, exceptions, controls, totals };
  }

  if (typeof window !== "undefined") window.Tieout = { reconcile };
  if (typeof module !== "undefined") module.exports = { reconcile };

  // node: run against the sibling fixture and print a summary.
  if (typeof require !== "undefined" && require.main === module) {
    const fs = require("fs");
    const data = JSON.parse(fs.readFileSync(require("path").join(__dirname, "data.json"), "utf8"));
    const r = reconcile(data);
    console.log(`Tieout engine on ${data.company} (${data.period})`);
    console.log("TOTALS:", JSON.stringify(r.totals));
    console.log(`\nEXCEPTIONS (${r.exceptions.length}):`);
    for (const e of r.exceptions) {
      const row = e.gl || e.bank;
      console.log(`  [${e.type}] ${row.date} ${row.party} ${(row.amount).toFixed(2)}` + (e.diff != null ? ` diff ${e.diff}` : ""));
    }
    console.log(`\nCONTROLS (${r.controls.length}):`);
    for (const c of r.controls) {
      if (c.type === "structuring") console.log(`  [structuring] ${c.party}: ${c.rows.length} payments just under ${c.threshold}`);
      else { const row = c.gl || c.bank; console.log(`  [${c.type}] ${row.date} ${row.party} ${(row.amount).toFixed(2)}` + (c.who ? ` (${c.who})` : "")); }
    }
  }
})();
