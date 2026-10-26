/* HomeFix front-end: talks to the Flask API */
const $ = (id) => document.getElementById(id);
const state = { appliance: null, problem: null, result: null };

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
async function api(url, opts) {
  const r = await fetch(url, opts);
  return r.json();
}

/* ---------- navigation ---------- */
function setStep(n) {
  document.querySelectorAll("#stepper li").forEach((li) => {
    const s = Number(li.dataset.step);
    li.classList.toggle("on", s === n);
    li.classList.toggle("done", s < n);
  });
  $("panel-appliance").classList.toggle("hidden", n !== 1);
  $("panel-problem").classList.toggle("hidden", n !== 2);
  $("panel-result").classList.toggle("hidden", n !== 3);
}
function showTab(name) {
  const fix = name === "fix";
  $("view-fix").classList.toggle("hidden", !fix);
  $("view-history").classList.toggle("hidden", fix);
  $("tab-fix").classList.toggle("active", fix);
  $("tab-history").classList.toggle("active", !fix);
  $("tab-fix").setAttribute("aria-selected", fix);
  $("tab-history").setAttribute("aria-selected", !fix);
  if (!fix) loadHistory();
}
$("tab-fix").onclick = () => showTab("fix");
$("tab-history").onclick = () => showTab("history");
$("back-appliance").onclick = () => setStep(1);
$("back-problem").onclick = () => setStep(2);

/* ---------- Module 1: appliances ---------- */
async function loadAppliances() {
  const list = await api("/api/appliances");
  $("appliance-grid").innerHTML = list
    .map((a) => `<button class="tile" data-id="${a.id}" data-name="${esc(a.name)}"><span class="ic">${a.icon}</span>${esc(a.name)}</button>`)
    .join("");
  document.querySelectorAll(".tile").forEach((t) => {
    t.onclick = () => selectAppliance({ id: Number(t.dataset.id), name: t.dataset.name });
  });
}

/* ---------- Module 2: problems ---------- */
async function selectAppliance(app) {
  state.appliance = app;
  $("problem-title").textContent = `What is wrong with your ${app.name}?`;
  $("symptom-input").value = "";
  $("match-note").classList.add("hidden");
  const probs = await api(`/api/problems/${app.id}`);
  renderProblems(probs);
  setStep(2);
}
function renderProblems(probs) {
  $("problem-list").innerHTML = probs
    .map((p) => `<li><button data-id="${p.id}" data-symptom="${esc(p.symptom)}">${esc(p.symptom)}</button></li>`)
    .join("");
  $("problem-list").querySelectorAll("button").forEach((b) => {
    b.onclick = () => selectProblem({ id: Number(b.dataset.id), symptom: b.dataset.symptom });
  });
}
async function findProblem() {
  const q = $("symptom-input").value.trim();
  if (!q) return;
  const matches = await api(`/api/match?appliance_id=${state.appliance.id}&q=${encodeURIComponent(q)}`);
  const note = $("match-note");
  note.classList.remove("hidden");
  if (matches.length) {
    note.textContent = "Best matches for what you described:";
    renderProblems(matches);
  } else {
    note.textContent = "No match found. Please pick one of the problems below.";
    renderProblems(await api(`/api/problems/${state.appliance.id}`));
  }
}
$("symptom-go").onclick = findProblem;
$("symptom-input").addEventListener("keydown", (e) => { if (e.key === "Enter") findProblem(); });

/* ---------- Module 3 + 4: causes, steps, safety ---------- */
async function selectProblem(p) {
  state.problem = p;
  const res = await api(`/api/troubleshoot/${p.id}`);
  state.result = res;
  $("result-title").textContent = `${state.appliance.name}: ${res.problem.symptom}`;
  $("causes").innerHTML = res.causes
    .map((c, i) => `
      <details class="cause" ${i === 0 ? "open" : ""} data-cause="${esc(c.cause)}">
        <summary><span class="rank">Cause ${i + 1}</span>${esc(c.cause)}</summary>
        <div class="cause-body">
          <ol>${c.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
          <div class="safety"><strong>⚠ Safety</strong>${esc(c.safety)}</div>
        </div>
      </details>`)
    .join("");
  const prev = $("prev-note");
  if (res.previous_failed_attempts > 0) {
    prev.textContent = `You have already tried this problem ${res.previous_failed_attempts} time(s) without success. Check your repair history.`;
    prev.classList.remove("hidden");
  } else {
    prev.classList.add("hidden");
  }
  $("outcome").classList.add("hidden");
  $("feedback").classList.remove("hidden");
  setStep(3);
}

/* ---------- Module 5: history + technician suggestion ---------- */
async function submitFeedback(resolved) {
  const open = document.querySelector(".cause[open]");
  const body = {
    problem_id: state.problem.id,
    resolved,
    cause_tried: open ? open.dataset.cause : "",
  };
  const res = await api("/api/history", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const box = $("outcome");
  box.classList.remove("hidden", "ok", "tech", "retry");
  if (resolved) {
    box.classList.add("ok");
    box.innerHTML = `<h3>Great, glad it is fixed!</h3><p>This repair has been saved in your history.</p>
      <button class="btn" id="again">Fix another problem</button>`;
  } else if (res.technician_suggested) {
    box.classList.add("tech");
    box.innerHTML = `<h3>Please contact a technician</h3><p>${esc(res.reason)}</p>
      <p>Do not open the appliance or try risky repairs yourself. Tell the technician what you already tried.</p>
      <button class="btn" id="again">Start over</button>`;
  } else {
    box.classList.add("retry");
    box.innerHTML = `<h3>Try the next cause</h3><p>Open the next cause above and follow its steps. If nothing works, we will suggest a technician.</p>`;
  }
  $("feedback").classList.add("hidden");
  const again = $("again");
  if (again) again.onclick = () => { setStep(1); };
  if (!resolved && !res.technician_suggested) {
    // allow another attempt
    setTimeout(() => $("feedback").classList.remove("hidden"), 0);
  }
}
$("fb-yes").onclick = () => submitFeedback(true);
$("fb-no").onclick = () => submitFeedback(false);

async function loadHistory() {
  const rows = await api("/api/history");
  const body = $("history-body");
  if (!rows.length) {
    body.innerHTML = `<p class="empty">No repairs saved yet. Solve a problem and it will appear here.</p>`;
    return;
  }
  body.innerHTML = `<div class="table-scroll"><table>
    <thead><tr><th>Date</th><th>Appliance</th><th>Problem</th><th>Cause tried</th><th>Result</th></tr></thead>
    <tbody>${rows.map((r) => `<tr>
      <td>${esc(r.created_at)}</td><td>${esc(r.appliance)}</td><td>${esc(r.symptom)}</td>
      <td>${esc(r.cause_tried || "-")}</td>
      <td>${r.resolved ? '<span class="badge ok">Solved</span>' : '<span class="badge no">Not solved</span>'}
          ${r.technician_suggested ? '<span class="badge tech">Technician advised</span>' : ""}</td>
    </tr>`).join("")}</tbody></table></div>`;
}
$("clear-history").onclick = async () => {
  if (confirm("Delete all saved repair history?")) {
    await api("/api/history", { method: "DELETE" });
    loadHistory();
  }
};

loadAppliances();
