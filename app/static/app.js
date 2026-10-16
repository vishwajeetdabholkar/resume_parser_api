const API = `${location.origin}/api/v1/resume`;
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const SNIPPETS = {
  curl: `curl -X POST '${API}/parse' \\
  -F 'file=@./your_cv_file.pdf'`,
  python: `import requests

with open("your_cv_file.pdf", "rb") as f:
    response = requests.post(
        "${API}/parse",
        files={"file": ("your_cv_file.pdf", f, "application/pdf")},
        timeout=60,
    )

response.raise_for_status()
print(response.json()["profile"])`,
  node: `import { readFile } from "node:fs/promises";

const form = new FormData();
const pdf = new Blob([await readFile("your_cv_file.pdf")], { type: "application/pdf" });
form.append("file", pdf, "your_cv_file.pdf");

const response = await fetch("${API}/parse", { method: "POST", body: form });
const body = await response.json();
if (!response.ok) throw new Error(body.error.message);

console.log(body.profile);`,
};

const escapeHtml = (text) => text.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);

function highlightJson(value) {
  const json = escapeHtml(JSON.stringify(value, null, 2));
  return json.replace(
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?/g,
    (match, string, colon, keyword) => {
      if (string) return `<span class="${colon ? "k" : "s"}">${string}</span>${colon || ""}`;
      return `<span class="${keyword ? "b" : "n"}">${match}</span>`;
    },
  );
}

const highlightCode = (code) =>
  escapeHtml(code).replace(/(["'`])(?:\\.|(?!\1)[^\\\n])*\1/g, (s) => `<span class="s">${s}</span>`);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function download(filename, value) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  link.click();
  URL.revokeObjectURL(url);
}

async function copy(text, button) {
  await navigator.clipboard.writeText(text);
  const label = button.textContent;
  button.textContent = "Copied";
  setTimeout(() => (button.textContent = label), 1200);
}

/* Routing */
function showPage() {
  const page = location.hash.slice(1) || "home";
  const target = document.getElementById(page) ? page : "home";
  $$(".page").forEach((section) => (section.hidden = section.id !== target));
  $$(".sidebar nav a").forEach((link) => link.classList.toggle("active", link.dataset.page === target));
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", showPage);
showPage();

/* Tabs */
function selectTab(group, name) {
  $$(`[data-tabs="${group}"] .tab`).forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
}

function showSnippet(name) {
  selectTab("snippet", name);
  $("#snippet").innerHTML = highlightCode(SNIPPETS[name]);
}

const dataView = { name: "example", value: null, sources: { example: "/example.json", schema: `${API}/schema` } };
const loaded = {};

async function showData(name) {
  selectTab("data", name);
  loaded[name] ??= await fetch(dataView.sources[name]).then((r) => r.json());
  dataView.name = name;
  dataView.value = loaded[name];
  $("#data-json").innerHTML = highlightJson(dataView.value);
}

$$("[data-tabs] .tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    const group = tab.closest("[data-tabs]").dataset.tabs;
    (group === "snippet" ? showSnippet : showData)(tab.dataset.tab);
  }),
);
$$("[data-copy]").forEach((button) =>
  button.addEventListener("click", () => copy($(`#${button.dataset.copy}`).textContent, button)),
);
$("#download").addEventListener("click", () => download(`resume-${dataView.name}.json`, dataView.value));

$$(".origin").forEach((node) => (node.textContent = location.origin));
showSnippet("curl");
showData("example");

/* Try it */
const tryPanel = $(".try");
const statusEl = $("#status");
const summaryEl = $("#summary");

function setStatus(message, kind = "") {
  statusEl.hidden = !message;
  statusEl.className = `status ${kind}`;
  statusEl.replaceChildren();
  if (kind === "loading") statusEl.append(el("span", "spinner"));
  statusEl.append(document.createTextNode(message));
}

const formatDate = ({ year, month }) => (year ? `${year}${month ? `-${String(month).padStart(2, "0")}` : ""}` : "?");
const plural = (count, unit) => `${count} ${unit}${count === 1 ? "" : "s"}`;

function renderSummary(result, seconds) {
  const { basics, professional_experiences: jobs, languages } = result.profile;
  const name = `${basics.first_name} ${basics.last_name}`.trim();
  summaryEl.replaceChildren(el("p", "name", name || "Unnamed candidate"));
  if (basics.profession) summaryEl.append(el("p", "headline", basics.profession));

  const facts = el("dl");
  [
    ["Email", basics.emails[0]],
    ["Phone", basics.phone_numbers[0]],
    ["Address", basics.address],
    ["Experience", plural(basics.total_experience_in_years, "year")],
    ["Languages", languages.map((language) => language.name).join(", ")],
    ["Links", basics.urls.length || null],
    ["Parsed in", `${seconds.toFixed(1)}s · ${result.cv_language.toUpperCase()}`],
  ]
    .filter(([, value]) => value)
    .forEach(([label, value]) => facts.append(el("dt", null, label), el("dd", null, value)));
  summaryEl.append(facts);

  if (jobs.length) {
    const list = el("ul", "jobs");
    jobs.slice(0, 4).forEach((job) => {
      const item = el("li", null, job.title || job.company);
      const period = `${formatDate(job.start_date)} – ${job.is_current ? "Present" : formatDate(job.end_date)}`;
      const duration = job.duration_in_months ? ` · ${plural(job.duration_in_months, "month")}` : "";
      item.append(el("small", null, `${job.title ? `${job.company} · ` : ""}${period}${duration}`));
      list.append(item);
    });
    summaryEl.append(el("h4", null, "Experience"), list);
  }

  if (basics.skills.length) {
    const chips = el("div", "chips");
    basics.skills.slice(0, 14).forEach((skill) => chips.append(el("span", "chip", skill)));
    summaryEl.append(el("h4", null, "Skills"), chips);
  }

  const actions = el("div", "actions");
  const viewJson = el("button", "btn btn-ghost btn-sm", "View JSON");
  const save = el("button", "btn btn-ghost btn-sm", "Download");
  viewJson.addEventListener("click", () => {
    location.hash = "extracted-data";
    showData("result");
  });
  save.addEventListener("click", () => download("resume.json", result));
  actions.append(viewJson, save);
  summaryEl.append(actions);
  summaryEl.hidden = false;
}

async function parse(file) {
  if (!file) return;
  summaryEl.hidden = true;
  setStatus(`Parsing ${file.name}…`, "loading");
  const form = new FormData();
  form.append("file", file);
  const started = performance.now();
  try {
    const response = await fetch(`${API}/parse`, { method: "POST", body: form });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error?.message || `Request failed (${response.status})`);
    setStatus("");
    loaded.result = body;
    $('[data-tab="result"]').hidden = false;
    renderSummary(body, (performance.now() - started) / 1000);
  } catch (error) {
    setStatus(error.message, "error");
  }
}

$("#file").addEventListener("change", (event) => {
  parse(event.target.files[0]);
  event.target.value = "";
});
["dragenter", "dragover"].forEach((type) =>
  tryPanel.addEventListener(type, (event) => {
    event.preventDefault();
    tryPanel.classList.add("dragging");
  }),
);
["dragleave", "drop"].forEach((type) =>
  tryPanel.addEventListener(type, (event) => {
    event.preventDefault();
    tryPanel.classList.remove("dragging");
  }),
);
tryPanel.addEventListener("drop", (event) => parse(event.dataTransfer.files[0]));
