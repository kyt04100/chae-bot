const $ = (id) => document.getElementById(id);

const escapeHtml = (s) => (s || "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));

async function loadStatus() {
  try {
    const r = await fetch("/api/status");
    const s = await r.json();
    const flags = [];
    if (s.api_key_set) flags.push("anthropic");
    if (s.s2_key_set) flags.push("s2");
    const flagStr = flags.length ? ` · keys: ${flags.join("+")}` : " · manual mode";
    const memStr = (s.memory_files && s.memory_files.length)
      ? ` · memory: ${s.memory_files.length} files`
      : " · no memory dir";
    $("status").textContent =
      `${s.pdfs} PDFs · ${s.chunks} chunks · ${s.papers} papers${flagStr}${memStr}`;
    if (!s.memory_files || s.memory_files.length === 0) {
      $("mem").checked = false;
      $("mem").disabled = true;
      $("mem-wrap").title = "no auto-memory found at " + (s.memory_dir || "~/.claude/projects/");
    }
  } catch (e) {
    $("status").textContent = "status unavailable";
  }
  $("endpoint").textContent = window.location.origin;
}

$("go").addEventListener("click", async () => {
  const bot = $("bot").value;
  const question = $("q").value.trim();
  if (!question) {
    $("q").focus();
    return;
  }
  const includeExternal = $("extern").checked;
  const includeMemory = $("mem").checked;

  $("go").disabled = true;
  $("go").textContent = "thinking…";
  $("hint").textContent = "검색 중…";

  try {
    const r = await fetch("/api/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot, question, include_external: includeExternal, include_memory: includeMemory }),
    });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(t || `HTTP ${r.status}`);
    }
    const data = await r.json();

    $("full").textContent = data.full_prompt;

    $("local-summary").textContent = `local hits (${data.local_hits.length})`;
    $("local").innerHTML = data.local_hits.length
      ? data.local_hits.map((h) => `
          <div class="hit">
            <b>${escapeHtml(h.paper_id)}</b>
            <span class="score">score=${h.score.toFixed(3)}</span>
            <div class="meta">${escapeHtml(h.title)} (${h.year || "?"})</div>
            <div>${escapeHtml(h.snippet)}…</div>
          </div>`).join("")
      : "<p><i>(no local hits)</i></p>";

    if (data.memory_block) {
      $("memory").textContent = data.memory_block;
      $("memory-summary").textContent = `memory injected (${data.memory_block.length.toLocaleString()} chars)`;
    } else {
      $("memory").textContent = "(memory not included)";
      $("memory-summary").textContent = "memory not injected";
    }

    $("external-summary").textContent = `external hits (${data.external_hits.length})`;
    $("external").innerHTML = data.external_hits.length
      ? data.external_hits.map((h) => `
          <div class="hit">
            <b>[${h.source}]</b> ${escapeHtml(h.title)}
            <div class="meta">${escapeHtml((h.authors || []).join(", "))} (${h.year || "?"})${h.venue ? " · " + escapeHtml(h.venue) : ""}</div>
            ${h.url ? `<div><a href="${h.url}" target="_blank" rel="noopener">${escapeHtml(h.url)}</a></div>` : ""}
            <div>${escapeHtml((h.abstract || "").slice(0, 320))}…</div>
          </div>`).join("")
      : "<p><i>(none — external search disabled or no results)</i></p>";

    document.querySelector(".output").hidden = false;
    document.querySelector(".output").scrollIntoView({ behavior: "smooth", block: "start" });
    $("hint").textContent = "프롬프트 준비 완료. copy prompt → claude에 붙여넣기.";
  } catch (e) {
    alert("error: " + e.message);
    $("hint").textContent = "오류 발생. 콘솔 확인.";
    console.error(e);
  } finally {
    $("go").disabled = false;
    $("go").textContent = "build prompt";
  }
});

$("copy").addEventListener("click", async () => {
  const text = $("full").textContent;
  try {
    await navigator.clipboard.writeText(text);
    $("copy").textContent = "copied ✓";
    setTimeout(() => ($("copy").textContent = "copy prompt"), 1500);
  } catch (e) {
    alert("clipboard write failed: " + e.message);
  }
});

$("q").addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    $("go").click();
  }
});

loadStatus();
