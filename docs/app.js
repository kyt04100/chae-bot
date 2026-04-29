const $ = (id) => document.getElementById(id);
const escapeHtml = (s) => (s || "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));

let PERSONAS = null;
let PAPERS = null;

async function init() {
  try {
    const [pRes, papRes] = await Promise.all([
      fetch("personas.json"),
      fetch("papers.json"),
    ]);
    if (!pRes.ok || !papRes.ok) throw new Error("data fetch failed");
    PERSONAS = await pRes.json();
    PAPERS = await papRes.json();
    const labCount = PAPERS.filter((p) => p.lab_paper).length;
    const absCount = PAPERS.filter((p) => p.abstract).length;
    $("status").textContent =
      `${PAPERS.length} papers · ${labCount} lab-authored · ${absCount} with arXiv abstract`;
  } catch (e) {
    $("status").textContent = "data load failed";
    console.error(e);
  }
}

function selectPapers({ topics, labOnly }) {
  let pool = PAPERS;
  if (labOnly) pool = pool.filter((p) => p.lab_paper);
  if (topics && topics.length) {
    const want = new Set(topics);
    // soft filter: keep papers tagged with any wanted topic, but if result < 8,
    // fall through to full pool (so general bot still gets coverage).
    const hit = pool.filter((p) => (p.topics || []).some((t) => want.has(t)));
    if (hit.length >= 6) pool = hit;
  }
  return pool;
}

function formatPaperBlock(p) {
  const head = `[${p.id}] ${p.title}`;
  const bits = [];
  if (p.authors && p.authors.length) bits.push(p.authors.join(", "));
  if (p.year) bits.push(String(p.year));
  if (p.venue) bits.push(p.venue);
  if (p.arxiv_url) bits.push(p.arxiv_url);
  const meta = bits.length ? " — " + bits.join(" / ") : "";
  const body = p.abstract ? `\n${p.abstract}` : "";
  return head + meta + body;
}

function buildPrompt({ bot, question, labOnly }) {
  const persona = PERSONAS[bot];
  const topicsByBot = {
    fas: ["fas", "ris", "multiple-access", "ai-comm"],
    trihybrid: ["tri-hybrid", "hybrid-beamforming", "rf-lens", "mmwave", "near-field", "xl-mimo"],
    general: null,
  };
  const picked = selectPapers({ topics: topicsByBot[bot], labOnly });
  const paperBlock = picked.map(formatPaperBlock).join("\n\n---\n\n");

  const parts = [
    "=== LAB CONTEXT ===\n" + persona.lab_context,
    persona.persona,
    "When you cite, use the bracket form like [paper-id] matching the IDs below. " +
      "If none of the listed papers are relevant, say so plainly — do not invent citations. " +
      "Where an abstract is missing, you may rely on the title/venue/year and your training-data " +
      "knowledge of the paper, but flag any uncertainty.",
    `=== AVAILABLE PAPERS (${picked.length} of ${PAPERS.length}) ===\n${paperBlock}\n=== END PAPERS ===`,
    `=== USER QUESTION ===\n${question}`,
  ];
  return { prompt: parts.join("\n\n"), papers: picked };
}

$("go").addEventListener("click", () => {
  if (!PERSONAS || !PAPERS) {
    alert("data not loaded yet");
    return;
  }
  const bot = $("bot").value;
  const question = $("q").value.trim();
  if (!question) {
    $("q").focus();
    return;
  }
  const labOnly = $("lab-only").checked;

  const { prompt, papers } = buildPrompt({ bot, question, labOnly });
  $("full").textContent = prompt;
  $("prompt-stats").textContent =
    `${prompt.length.toLocaleString()} chars · ${papers.length} papers included`;

  $("papers-summary").textContent = `papers in prompt (${papers.length})`;
  $("papers").innerHTML = papers.map((p) => `
    <div class="paper">
      <b>${escapeHtml(p.id)}</b> · ${escapeHtml(p.title)}
      <div class="meta">${escapeHtml((p.authors || []).join(", "))} (${p.year || "?"}) · ${escapeHtml(p.venue || "")}${p.lab_paper ? " · lab" : ""}</div>
      ${p.arxiv_url ? `<div><a href="${p.arxiv_url}" target="_blank" rel="noopener">${escapeHtml(p.arxiv_url)}</a></div>` : ""}
      ${p.abstract ? `<div class="meta" style="margin-top:0.25rem">${escapeHtml(p.abstract.slice(0, 280))}…</div>` : ""}
    </div>`).join("");

  document.querySelector(".output").hidden = false;
  document.querySelector(".output").scrollIntoView({ behavior: "smooth", block: "start" });
});

$("copy").addEventListener("click", async () => {
  const text = $("full").textContent;
  try {
    await navigator.clipboard.writeText(text);
    $("copy").textContent = "copied ✓";
    setTimeout(() => ($("copy").textContent = "copy prompt"), 1500);
  } catch (e) {
    alert("clipboard error: " + e.message);
  }
});

$("q").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") $("go").click();
});

init();
