// Run the browser model from web/template.html on web/adi_data.json and
// print the largest relative gap from the Python baseline, per scenario.
// Usage: node tests/js/parity.js web/template.html web/adi_data.json
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const D = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const start = html.indexOf("// ---------------------------------------------------------------- model");
const end = html.indexOf("// ------------------------------------------------------------- helpers");
const Y = D.per_year.year, N = Y.length, A0 = D.assumptions;
const ELSE = ["Household goods", "Technology", "Vacations", "Other necessities"];
let S = { scen: "A", dollars: "real", retire: A0.retire_age, ret: A0.real_return_accumulation, home: 1, down: A0.down_payment, care: 1 };
eval(html.slice(start, end) + "; globalThis.compute = compute;");
for (const scen of ["A", "B"]) {
  const rows = compute(scen);
  let maxErr = 0, maxRet = 0;
  rows.forEach((r, i) => {
    maxErr = Math.max(maxErr, Math.abs(r.cost / D.baseline[scen].cost_pretax[i] - 1));
    maxRet = Math.max(maxRet, Math.abs(r.cat["Retirement saving"] / D.baseline[scen].retirement_saving[i] - 1));
  });
  console.log(JSON.stringify({ scen, cost: maxErr, retirement: maxRet }));
}
