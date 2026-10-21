"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("query-form");
const question = byId("question");
const submit = byId("submit-query");
const suggestions = document.querySelectorAll(".suggestion");
let querying = false;
let healthPending = false;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function readable(value) {
  if (value === undefined || value === null) return "Not provided";
  return typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
}

function detailCard(title) {
  const card = element("details");
  card.append(element("summary", "", title));
  const body = element("div", "source-content");
  card.append(body);
  return {card, body};
}

function renderResult(data, askedQuestion) {
  byId("result-question").textContent = askedQuestion;
  byId("answer").textContent = typeof data.answer === "string" && data.answer.trim() ? data.answer : "No assessment was returned. Inspect the available evidence or try a more specific question.";
  const state = ["ok", "partial", "unavailable"].includes(data.status) ? data.status : "unavailable";
  const badge = byId("result-status");
  badge.className = `status-badge ${state}`;
  badge.textContent = {ok: "Complete", partial: "Partial evidence", unavailable: "Unavailable"}[state];
  const seconds = Number(data.elapsed_seconds);
  byId("result-time").textContent = Number.isFinite(seconds) && seconds >= 0 ? `${seconds.toFixed(1)}s` : "";
  const citations = Array.isArray(data.citations) ? data.citations : [];
  const evidence = Array.isArray(data.evidence) ? data.evidence : [];
  byId("source-count").textContent = `${citations.length} cited`;
  const sourceList = byId("citations");
  sourceList.replaceChildren();
  if (!citations.length) sourceList.append(element("p", "evidence-empty", "No citations were returned for this assessment."));
  citations.forEach((citation, index) => {
    if (!citation || typeof citation !== "object") return;
    const title = citation.source || citation.kind || "Source";
    const {card, body} = detailCard(`${String(index + 1).padStart(2, "0")} · ${readable(title)}`);
    for (const [field, label] of [["record_id", "Record"], ["kind", "Type"], ["chunk_index", "Section"], ["chunk_id", "Chunk"], ["uri", "Reference"]]) {
      if (citation[field] !== undefined && citation[field] !== null) body.append(element("p", "", `${label}: ${readable(citation[field])}`));
    }
    const quote = citation.quote || citation.evidence;
    if (quote) body.append(element("blockquote", "", readable(quote)));
    const matching = evidence.filter((entry) => Array.isArray(entry?.citations) && entry.citations.some((item) => item && (JSON.stringify(item) === JSON.stringify(citation) || (citation.record_id != null && item.record_id === citation.record_id && item.source === citation.source))));
    matching.forEach((entry) => body.append(element("pre", "", readable(entry.data))));
    if (!body.childNodes.length) body.append(element("pre", "", readable(citation)));
    sourceList.append(card);
  });
  const evidenceList = byId("evidence");
  evidenceList.replaceChildren();
  if (evidence.length) evidenceList.append(element("p", "evidence-group-label", "SUPPORTING RECORDS"));
  const toolLabels = {query_fleet_data: "Fleet signals", search_documents: "Manual procedures", query_parts: "Parts availability", query_knowledge_graph: "Related maintenance knowledge"};
  evidence.forEach((entry, index) => {
    if (!entry || typeof entry !== "object") return;
    const label = toolLabels[entry.tool] || "Supporting evidence";
    const {card, body} = detailCard(`${label} · ${entry.status === "ok" ? "Available" : entry.status === "empty" ? "No records" : entry.status === "partial" ? "Partial" : entry.status === "unavailable" || entry.status === "error" ? "Unavailable" : `Record ${index + 1}`}`);
    if (entry.source_time) body.append(element("p", "", `Source time: ${readable(entry.source_time)}`));
    if (entry.error) body.append(element("p", "", readable(entry.error)));
    body.append(element("pre", "", readable(entry.data)));
    evidenceList.append(card);
  });
  byId("result").hidden = false;
  byId("result-title").focus({preventScroll: true});
}

async function refreshHealth() {
  if (healthPending) return;
  healthPending = true;
  byId("refresh-health").disabled = true;
  try {
    const response = await fetch("/api/health", {headers: {Accept: "application/json"}});
    const data = await response.json();
    if (!response.ok && !data.services) throw new Error("Health check unavailable");
    const serviceList = byId("service-status");
    serviceList.replaceChildren();
    for (const [key, label] of [["database", "Database"], ["parts", "Parts API"], ["model", "Local model"]]) {
      const online = data.services?.[key] === true;
      const status = element("span", `service${online ? "" : " offline"}`, `${label} · ${online ? "Online" : "Unavailable"}`);
      serviceList.append(status);
    }
    const summary = byId("data-summary");
    summary.replaceChildren();
    for (const [key, label] of [["sensor_readings", "Sensor readings"], ["maintenance_logs", "Maintenance records"], ["document_chunks", "Manual sections"], ["relationships", "Graph relationships"]]) {
      const count = data.counts?.[key];
      const available = typeof count === "number" && Number.isFinite(count) && count >= 0;
      const stat = element("div", "data-stat");
      stat.append(element("strong", "", available ? count.toLocaleString() : "—"), element("span", "", label));
      summary.append(stat);
    }
    summary.hidden = !summary.childNodes.length;
    const date = data.source_time ? new Date(data.source_time) : null;
    const stamp = date && !Number.isNaN(date.getTime()) ? `Latest source record: ${date.toLocaleString()}.` : "";
    byId("health-note").textContent = `${data.status === "degraded" ? "Some services are unavailable. Results may be incomplete. " : ""}${stamp}`;
  } catch (_) {
    byId("service-status").replaceChildren(element("span", "service offline", "Service status unavailable"));
    byId("health-note").textContent = "Could not check local services. Refresh to try again.";
    byId("data-summary").hidden = true;
  } finally {
    healthPending = false;
    byId("refresh-health").disabled = false;
  }
}

suggestions.forEach((button) => button.addEventListener("click", () => {
  question.value = button.dataset.prompt;
  question.focus();
}));
byId("refresh-health").addEventListener("click", refreshHealth);
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (querying) return;
  const askedQuestion = question.value.trim();
  if (!askedQuestion) { question.focus(); return; }
  querying = true;
  submit.disabled = true;
  question.readOnly = true;
  suggestions.forEach((button) => { button.disabled = true; });
  byId("query-error").hidden = true;
  byId("result").hidden = true;
  byId("progress").hidden = false;
  byId("elapsed").textContent = "0s";
  const started = Date.now();
  const timer = setInterval(() => { byId("elapsed").textContent = `${Math.floor((Date.now() - started) / 1000)}s`; }, 1000);
  try {
    const response = await fetch("/api/query", {method: "POST", headers: {"Content-Type": "application/json", Accept: "application/json"}, body: JSON.stringify({question: askedQuestion})});
    let data;
    try { data = await response.json(); } catch (_) { throw new Error("The local server did not return a readable response. Please try again."); }
    if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "The investigation could not be completed. Check local services and try again.");
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("The local server returned an unexpected response. Please try again.");
    renderResult(data, askedQuestion);
  } catch (error) {
    byId("query-error").textContent = error instanceof TypeError ? "Could not reach the local server. Check that the workspace is running, then try again. Your question has been kept." : error.message;
    byId("query-error").hidden = false;
  } finally {
    clearInterval(timer);
    querying = false;
    submit.disabled = false;
    question.readOnly = false;
    suggestions.forEach((button) => { button.disabled = false; });
    byId("progress").hidden = true;
  }
});
refreshHealth();
