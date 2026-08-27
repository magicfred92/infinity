// Infinity Job Radar — front-end. No build step: plain fetch + DOM.
(() => {
  "use strict";

  const OWNER = "magicfred92";
  const REPO = "infinity";
  const BRANCH = "main";
  const CONFIG_PATH = "scraper/sources_config.json";
  const WORKFLOW_FILE = "scrape.yml";
  const TOKEN_KEY = "infinity_job_radar_gh_token";

  const state = {
    jobs: [],
    sourcesConfig: [], // read-only mirror for display
    filters: { search: "", region: "", sources: new Set(), minScore: 0, sort: "score" },
  };

  // ---------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------

  async function loadJobs() {
    try {
      const res = await fetch("data/jobs.json", { cache: "no-store" });
      const data = await res.json();
      state.jobs = data.jobs || [];
      renderProfileLine(data.profile);
      renderLastUpdated(data.generated_at);
      renderStatusBanner(data);
      state.filters.sources = new Set((data.jobs || []).map((j) => j.source));
    } catch (err) {
      console.error("Failed to load jobs.json", err);
      showBanner("Impossible de charger les offres pour le moment.", "error");
    }
  }

  async function loadSourcesConfigMirror() {
    try {
      const res = await fetch("data/sources_config.json", { cache: "no-store" });
      state.sourcesConfig = await res.json();
    } catch (err) {
      console.warn("No sources_config mirror yet", err);
      state.sourcesConfig = [];
    }
    renderSourceFilter();
    renderSourcesTable();
  }

  function renderProfileLine(profile) {
    const el = document.getElementById("profile-line");
    if (!profile) {
      el.textContent = "Aucune donnée pour l'instant — le premier scraping n'a pas encore tourné.";
      return;
    }
    el.textContent = `${profile.headline} — ${profile.target_regions.join(", ")}`;
  }

  function renderLastUpdated(generatedAt) {
    const el = document.getElementById("last-updated");
    el.textContent = generatedAt ? new Date(generatedAt).toLocaleString("fr-CH") : "jamais encore";
  }

  function renderStatusBanner(data) {
    const banner = document.getElementById("status-banner");
    if (!data.generated_at) {
      showBanner(
        "Aucune offre pour l'instant. Le scraping tourne automatiquement chaque jour via " +
          "GitHub Actions, ou lance-le manuellement ci-dessous une fois un token configuré.",
        "info"
      );
      return;
    }
    const failed = Object.entries(data.source_status || {}).filter(([, s]) => !s.ok);
    if (failed.length) {
      showBanner(
        "Échec du scraping pour : " + failed.map(([name]) => name).join(", ") +
          ". Voir les logs GitHub Actions pour le détail.",
        "error"
      );
    } else {
      banner.hidden = true;
    }
  }

  function showBanner(text, kind) {
    const banner = document.getElementById("status-banner");
    banner.textContent = text;
    banner.hidden = false;
    banner.dataset.kind = kind || "info";
  }

  // ---------------------------------------------------------------------
  // Filtering / rendering job list
  // ---------------------------------------------------------------------

  function scoreTier(score) {
    if (score >= 66) return "high";
    if (score >= 33) return "mid";
    return "low";
  }

  function applyFilters() {
    const { search, region, sources, minScore, sort } = state.filters;
    let list = state.jobs.filter((job) => {
      if (job.score < minScore) return false;
      if (region) {
        if (region === "__unknown" ? job.region : job.region !== region) return false;
      }
      if (sources.size && !sources.has(job.source)) return false;
      if (search) {
        const haystack = `${job.title} ${job.company} ${job.summary} ${(job.matched_keywords || []).join(" ")}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });

    list.sort((a, b) => {
      if (sort === "date") {
        return (b.date_posted || "").localeCompare(a.date_posted || "");
      }
      return b.score - a.score;
    });

    renderJobList(list);
  }

  function renderJobList(list) {
    const container = document.getElementById("job-list");
    const template = document.getElementById("job-card-template");
    const emptyState = document.getElementById("empty-state");
    const countEl = document.getElementById("results-count");

    container.innerHTML = "";
    countEl.textContent = `${list.length} offre${list.length === 1 ? "" : "s"}`;
    emptyState.hidden = list.length !== 0;

    for (const job of list) {
      const node = template.content.cloneNode(true);
      node.querySelector(".job-title").textContent = job.title;
      const scoreEl = node.querySelector(".job-score");
      scoreEl.textContent = `${job.score}%`;
      scoreEl.dataset.tier = scoreTier(job.score);
      node.querySelector(".job-company").textContent = job.company || "Entreprise non précisée";
      node.querySelector(".job-location").textContent = job.location || "Lieu non précisé";
      node.querySelector(".job-source").textContent = job.source;
      node.querySelector(".job-summary").textContent = job.summary || "";
      const kw = job.matched_keywords || [];
      node.querySelector(".job-keywords").textContent = kw.length
        ? "Correspondances : " + kw.slice(0, 8).join(", ")
        : "";
      const link = node.querySelector(".job-link");
      link.href = job.url;
      container.appendChild(node);
    }
  }

  function renderSourceFilter() {
    const container = document.getElementById("source-filter");
    const sources = [...new Set(state.jobs.map((j) => j.source).concat(state.sourcesConfig.map((s) => s.name)))];
    container.innerHTML = "";
    for (const source of sources) {
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = true;
      checkbox.value = source;
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.filters.sources.add(source);
        else state.filters.sources.delete(source);
        applyFilters();
      });
      label.appendChild(checkbox);
      label.append(" " + source);
      container.appendChild(label);
    }
  }

  function wireFilterControls() {
    document.getElementById("search-input").addEventListener("input", (e) => {
      state.filters.search = e.target.value;
      applyFilters();
    });
    document.getElementById("region-filter").addEventListener("change", (e) => {
      state.filters.region = e.target.value;
      applyFilters();
    });
    const minScore = document.getElementById("min-score");
    const minScoreOutput = document.getElementById("min-score-output");
    minScore.addEventListener("input", (e) => {
      state.filters.minScore = Number(e.target.value);
      minScoreOutput.textContent = e.target.value;
      applyFilters();
    });
    document.getElementById("sort-select").addEventListener("change", (e) => {
      state.filters.sort = e.target.value;
      applyFilters();
    });
  }

  // ---------------------------------------------------------------------
  // GitHub token (browser-only, never sent anywhere but api.github.com)
  // ---------------------------------------------------------------------

  function getToken() {
    try {
      return localStorage.getItem(TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  function setToken(value) {
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
      // Some browsers (Safari private mode, strict privacy settings) accept
      // localStorage writes silently but never actually persist them — a
      // failed save would otherwise look identical to a successful one, so
      // read back what was just written to be sure.
      return getToken() === value;
    } catch {
      return false;
    }
  }

  function refreshTokenStatus() {
    const status = document.getElementById("gh-token-status");
    const hasToken = !!getToken();
    status.textContent = hasToken
      ? "Token GitHub enregistré dans ce navigateur — écriture activée."
      : "Aucun token GitHub enregistré — lecture seule.";
    document.getElementById("trigger-scrape").disabled = !hasToken;
  }

  function wireTokenModal() {
    const modal = document.getElementById("token-modal");
    const input = document.getElementById("token-input");
    const feedback = document.getElementById("token-feedback");

    const showFeedback = (text, ok) => {
      feedback.textContent = text;
      feedback.hidden = false;
      feedback.style.color = ok ? "var(--score-high)" : "var(--score-low)";
    };

    document.getElementById("gh-token-edit").addEventListener("click", () => {
      input.value = getToken();
      feedback.hidden = true;
      modal.hidden = false;
    });
    document.getElementById("token-cancel").addEventListener("click", () => {
      modal.hidden = true;
    });
    document.getElementById("token-save").addEventListener("click", () => {
      const value = input.value.trim();
      if (!value) {
        showFeedback("Le champ est vide — colle ton token avant d'enregistrer.", false);
        return;
      }
      const ok = setToken(value);
      if (!ok) {
        showFeedback(
          "Échec de l'enregistrement : ce navigateur bloque le stockage local " +
            "(mode privé ou réglages de confidentialité stricts). Essaie en navigation normale.",
          false
        );
        return;
      }
      refreshTokenStatus();
      showFeedback("✅ Token enregistré.", true);
      setTimeout(() => {
        modal.hidden = true;
      }, 800);
    });
    document.getElementById("token-clear").addEventListener("click", () => {
      setToken("");
      input.value = "";
      refreshTokenStatus();
      showFeedback("Token effacé.", true);
      setTimeout(() => {
        modal.hidden = true;
      }, 600);
    });
  }

  // ---------------------------------------------------------------------
  // GitHub API — reading/writing scraper/sources_config.json, and
  // triggering the scrape workflow on demand. All calls go straight from
  // this page to api.github.com (which supports CORS); nothing is
  // proxied through a third party.
  // ---------------------------------------------------------------------

  function b64EncodeUnicode(str) {
    return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (_, p1) => String.fromCharCode("0x" + p1)));
  }

  function b64DecodeUnicode(str) {
    return decodeURIComponent(
      atob(str)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
  }

  async function ghApi(path, options = {}) {
    const token = getToken();
    if (!token) throw new Error("Aucun token GitHub configuré.");
    const res = await fetch(`https://api.github.com${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        ...(options.headers || {}),
      },
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`GitHub API ${res.status}: ${body.slice(0, 300)}`);
    }
    return res.status === 204 ? null : res.json();
  }

  async function fetchLiveSourcesConfig() {
    const data = await ghApi(`/repos/${OWNER}/${REPO}/contents/${CONFIG_PATH}?ref=${BRANCH}`);
    return { list: JSON.parse(b64DecodeUnicode(data.content)), sha: data.sha };
  }

  async function saveLiveSourcesConfig(list, sha, message) {
    await ghApi(`/repos/${OWNER}/${REPO}/contents/${CONFIG_PATH}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        content: b64EncodeUnicode(JSON.stringify(list, null, 2) + "\n"),
        sha,
        branch: BRANCH,
      }),
    });
  }

  async function triggerWorkflow() {
    await ghApi(`/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: BRANCH }),
    });
  }

  // ---------------------------------------------------------------------
  // "Gérer les sites" panel
  // ---------------------------------------------------------------------

  function renderSourcesTable() {
    const body = document.getElementById("sources-table-body");
    body.innerHTML = "";
    const statusBySource = {};
    for (const job of state.jobs) statusBySource[job.source] = (statusBySource[job.source] || 0) + 1;

    for (const source of state.sourcesConfig) {
      const tr = document.createElement("tr");

      const enabledTd = document.createElement("td");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = source.enabled !== false;
      checkbox.addEventListener("change", () => toggleSource(source.id, checkbox.checked));
      enabledTd.appendChild(checkbox);

      const nameTd = document.createElement("td");
      nameTd.textContent = source.name;

      const urlTd = document.createElement("td");
      urlTd.textContent = source.base_url;

      const countTd = document.createElement("td");
      countTd.textContent = statusBySource[source.name] ?? "—";

      const actionsTd = document.createElement("td");
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "Retirer";
      removeBtn.addEventListener("click", () => removeSource(source.id));
      actionsTd.appendChild(removeBtn);

      tr.append(enabledTd, nameTd, urlTd, countTd, actionsTd);
      body.appendChild(tr);
    }
  }

  async function withWriteFeedback(elementId, fn) {
    const el = document.getElementById(elementId);
    el.hidden = false;
    el.textContent = "…";
    try {
      await fn();
      el.textContent = "✅ Fait. Le prochain scraping planifié (ou manuel) prendra en compte ce changement.";
      await loadSourcesConfigMirrorSoon();
    } catch (err) {
      console.error(err);
      el.textContent = "❌ " + err.message;
    }
  }

  async function loadSourcesConfigMirrorSoon() {
    // The GitHub Pages mirror only updates once the next scrape workflow
    // commits it, so re-fetch the live config instead for immediate
    // feedback in the table.
    try {
      const { list } = await fetchLiveSourcesConfig();
      state.sourcesConfig = list;
      renderSourceFilter();
      renderSourcesTable();
    } catch (err) {
      console.warn("Could not refresh live config", err);
    }
  }

  function toggleSource(id, enabled) {
    withWriteFeedback("add-source-feedback", async () => {
      const { list, sha } = await fetchLiveSourcesConfig();
      const updated = list.map((s) => (s.id === id ? { ...s, enabled } : s));
      await saveLiveSourcesConfig(updated, sha, `chore: ${enabled ? "enable" : "disable"} source ${id}`);
    });
  }

  function removeSource(id) {
    if (!confirm("Retirer définitivement ce site de la liste ?")) return;
    withWriteFeedback("add-source-feedback", async () => {
      const { list, sha } = await fetchLiveSourcesConfig();
      const updated = list.filter((s) => s.id !== id);
      await saveLiveSourcesConfig(updated, sha, `chore: remove source ${id}`);
    });
  }

  function slugify(name) {
    return name
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function wireAddSourceForm() {
    document.getElementById("add-source-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const form = e.target;
      const values = Object.fromEntries(new FormData(form).entries());
      const newSource = {
        id: slugify(values.name) || `site_${Date.now()}`,
        name: values.name.trim(),
        enabled: true,
        base_url: values.base_url.trim().replace(/\/$/, ""),
        search_path: values.search_path.trim(),
        term_param: (values.term_param || "term").trim(),
        location_param: values.location_param.trim() || null,
        page_param: "page",
        detail_link_hints: values.detail_link_hints
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        max_pages_per_query: 1,
        max_jobs: 40,
        notes: "Ajouté depuis l'application le " + new Date().toISOString().slice(0, 10),
      };

      withWriteFeedback("add-source-feedback", async () => {
        const { list, sha } = await fetchLiveSourcesConfig();
        if (list.some((s) => s.id === newSource.id)) {
          throw new Error("Un site avec un identifiant équivalent existe déjà.");
        }
        await saveLiveSourcesConfig([...list, newSource], sha, `feat: add source ${newSource.id}`);
        form.reset();
      });
    });
  }

  function wireTriggerScrape() {
    document.getElementById("trigger-scrape").addEventListener("click", () => {
      withWriteFeedback("trigger-feedback", async () => {
        await triggerWorkflow();
      });
    });
  }

  function wireSourcesToggle() {
    const toggle = document.getElementById("sources-toggle");
    const body = document.getElementById("sources-body");
    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!expanded));
      body.hidden = expanded;
    });
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------

  async function init() {
    wireFilterControls();
    wireTokenModal();
    wireAddSourceForm();
    wireTriggerScrape();
    wireSourcesToggle();
    refreshTokenStatus();

    await loadJobs();
    await loadSourcesConfigMirror();
    applyFilters();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
