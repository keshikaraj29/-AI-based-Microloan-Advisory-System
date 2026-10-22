"use strict";
(() => {
  const byId = id => document.getElementById(id);
  const number = value => value !== null && value !== undefined && Number.isFinite(Number(value));
  const fmt = value => number(value) ? Number(value).toLocaleString("en-IN") : "—";
  const inr = value => number(value) ? new Intl.NumberFormat("en-IN", {style: "currency", currency: "INR", maximumFractionDigits: 2}).format(value) : "Not provided";
  const pageQuery = new URLSearchParams(location.search);
  const knownPurposes = Array.from(byId("purpose-filter").options).map(option => option.value);
  function purposeFromURL() {
    const params = new URLSearchParams(location.search);
    // An explicit empty value means the whole corpus, including application links.
    // An omitted value may use the server's application-specific initial scope.
    return params.has("purpose") ? params.get("purpose") :
      (params.get("application_id") ? byId("main").dataset.purpose || "" : "");
  }
  let requestedPurpose = purposeFromURL();
  let purposeFilter = knownPurposes.includes(requestedPurpose) ? requestedPurpose : "";
  byId("purpose-filter").value = purposeFilter;
  if (requestedPurpose && !purposeFilter) byId("cohort-status").textContent = "Unrecognized purpose · showing the complete research corpus";
  const percent = value => number(value) ? `${(Number(value) * 100).toFixed(1)}%` : "Not measured";
  const decimal = value => number(value) ? Number(value).toFixed(3) : "—";
  const human = value => String(value ?? "Not available").replaceAll("_", " ");
  const setText = (id, value) => { byId(id).textContent = String(value); };
  function node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text);
    if (className) element.className = className;
    return element;
  }
  function empty(container, message) {
    container.replaceChildren(node("p", message, "empty-state"));
  }
  async function getJSON(url, controller = new AbortController()) {
    const timeout = window.setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(url, {signal: controller.signal, credentials: "same-origin", headers: {Accept: "application/json"}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "The dataset could not be loaded. Please retry.");
      return data;
    } finally { window.clearTimeout(timeout); }
  }
  function fillClusters(clusters) {
    const container = byId("cluster-chart");
    container.replaceChildren();
    const filter = byId("cluster-filter");
    const selected = filter.value;
    filter.replaceChildren(node("option", "All groups"));
    filter.firstChild.value = "";
    if (!clusters.length) return empty(container, "No borrower clusters are available for this dataset.");
    const maximum = Math.max(...clusters.map(item => Number(item.count) || 0), 1);
    clusters.forEach(item => {
      const row = node("div", undefined, "cluster-row");
      const heading = node("div", undefined, "cluster-row-header");
      heading.append(node("strong", item.label || `Group ${item.id}`), node("span", `${fmt(item.count)} records`));
      const track = node("div", undefined, "cluster-track");
      track.setAttribute("aria-hidden", "true");
      const bar = node("span");
      bar.style.width = `${Math.max(0, Math.min(100, (Number(item.count) || 0) / maximum * 100))}%`;
      track.append(bar);
      row.append(heading, track, node("p", `Resolved-loan repayment: ${percent(item.repayment_rate)} · Mean loan: ${inr(item.mean_loan_amount)}`, "cluster-meta"));
      container.append(row);
      const option = node("option", item.label || `Group ${item.id}`);
      option.value = String(item.id);
      filter.append(option);
    });
    filter.value = selected;
  }
  function fillTopics(topics) {
    const container = byId("topic-list");
    container.replaceChildren();
    if (!topics.length) return empty(container, "Not enough borrower narratives to identify topics.");
    topics.slice(0, 6).forEach(item => {
      const row = node("div", undefined, "topic-row");
      const heading = node("div", undefined, "topic-row-header");
      heading.append(node("strong", item.label), node("span", `${fmt(item.count)} narratives`));
      const keywords = node("div", undefined, "topic-keywords");
      (item.keywords || []).slice(0, 7).forEach(keyword => keywords.append(node("span", typeof keyword === "string" ? keyword : keyword.keyword, "keyword")));
      row.append(heading, keywords);
      container.append(row);
    });
  }
  function fillStructures(structures) {
    const container = byId("loan-structures");
    container.replaceChildren();
    if (!structures.length) return empty(container, "No term-level outcome comparisons are available.");
    structures.forEach(item => {
      const row = node("div", undefined, "structure-item");
      const label = node("div");
      label.append(node("strong", `${fmt(item.term_months)}-month term`), node("small", `${fmt(item.resolved_count)} resolved of ${fmt(item.count)} sampled loans`));
      row.append(label, node("b", percent(item.repayment_rate)));
      container.append(row);
    });
  }
  function fillCorrelations(items) {
    const container = byId("correlation-list");
    container.replaceChildren();
    if (!items.length) return empty(container, "There are too few comparable outcomes to calculate correlations.");
    items.slice(0, 8).forEach(item => {
      const row = node("div", undefined, "correlation-item");
      const label = node("div");
      label.append(node("strong", human(item.feature)), node("small", `${human(item.outcome)} · n = ${fmt(item.n)}`));
      row.append(label, node("b", decimal(item.correlation)));
      container.append(row);
    });
  }
  function fillSources(sources) {
    const container = byId("source-list");
    container.replaceChildren();
    if (!sources.length) return empty(container, "Source provenance is not available.");
    sources.forEach(source => {
      const row = node("div", undefined, "source-row");
      if (typeof source === "string") row.append(node("span", source));
      else {
        const description = node("div");
        description.append(node("span", source.name || source.filename || "Source file"));
        if (source.scope) description.append(node("p", source.scope, "small-note"));
        if (source.sha256) description.append(node("code", `SHA-256: ${source.sha256}`, "source-hash"));
        row.append(description, node("small", `${fmt(source.records)} records${source.currency ? ` · ${source.currency}` : ""}`));
      }
      container.append(row);
    });
  }
  let summaryRequest = 0;
  let summaryController = null;
  async function loadSummary() {
    const requestId = ++summaryRequest;
    if (summaryController) summaryController.abort();
    const controller = new AbortController();
    summaryController = controller;
    const section = byId("overview");
    const status = byId("research-status");
    section.setAttribute("aria-busy", "true");
    status.classList.remove("error");
    status.textContent = "Loading the local research summary…";
    byId("research-retry").hidden = true;
    try {
      const summaryParams = new URLSearchParams();
      if (purposeFilter) summaryParams.set("purpose", purposeFilter);
      const data = await getJSON(`/api/research/summary?${summaryParams}`, controller);
      if (requestId !== summaryRequest) return;
      if (data.fx && byId("fx-note")) setText("fx-note", `Pinned conversion: ₹${Number(data.fx.usd_to_inr).toLocaleString("en-IN", {maximumFractionDigits: 4})} per source-currency unit, reference date ${data.fx.rate_date}. This is a documented snapshot, not a live quote. Source records retain their original currency.`);
      const dataset = data.dataset || {};
      const metrics = data.metrics || {};
      setText("cohort-status", `${purposeFilter ? human(purposeFilter) : "All loan purposes"} · ${fmt(dataset.records)} analyzed records${metrics.model_scope ? " · clustering model fitted on the complete corpus" : ""}`);
      if (requestedPurpose && !purposeFilter && !knownPurposes.includes(requestedPurpose)) setText("cohort-status", `Unrecognized requested purpose · showing all ${fmt(dataset.records)} research records`);
      setText("stat-records", fmt(dataset.records));
      setText("stat-source-records", `${fmt(dataset.source_records)} valid source loan records`);
      setText("stat-narratives", fmt(dataset.narratives));
      setText("stat-repayment", percent(metrics.repayment_rate));
      setText("stat-silhouette", decimal(metrics.silhouette_score));
      setText("primary-insight", (data.insights || [])[0] || "Compare repayment only among resolved loans; unresolved loans have no final outcome yet.");
      fillClusters(data.clusters || []);
      fillTopics(data.topics || []);
      fillStructures(data.loan_structures || []);
      fillCorrelations(data.correlations || []);
      fillSources(dataset.sources || []);
      const sentiment = byId("sentiment-comparison");
      sentiment.replaceChildren();
      (data.sentiment || []).forEach(item => {
        const row = node("div", undefined, "structure-item");
        const label = node("div");
        label.append(node("strong", human(item.label)), node("small", `${fmt(item.resolved_count)} resolved · ${fmt(item.count)} narratives`));
        row.append(label, node("b", percent(item.repayment_rate)));
        sentiment.append(row);
      });
      if (!sentiment.children.length) empty(sentiment, "Not enough narratives for sentiment comparisons.");
      const regions = byId("region-comparison");
      regions.replaceChildren();
      [...(data.regions || [])].sort((a, b) => b.count - a.count).slice(0, 5).forEach(item => {
        const row = node("div", undefined, "structure-item");
        const label = node("div");
        label.append(node("strong", item.state), node("small", `${fmt(item.resolved_count)} resolved of ${fmt(item.count)} sampled loans`));
        row.append(label, node("b", percent(item.repayment_rate)));
        regions.append(row);
      });
      if (!regions.children.length) empty(regions, "No regional comparisons are available.");
      if (Array.isArray(data.limitations) && data.limitations.length) byId("limitations-list").replaceChildren(...data.limitations.map(text => node("li", text)));
      const methodDetails = [];
      if (number(metrics.davies_bouldin_score)) methodDetails.push(`Davies–Bouldin index: ${decimal(metrics.davies_bouldin_score)} (lower indicates tighter, better separated clusters).`);
      if (number(metrics.resolved_count)) methodDetails.push(`${fmt(metrics.resolved_count)} resolved loans; ${fmt(metrics.unresolved_count)} unresolved loans.`);
      const methods = data.methods || {};
      if (methods.sampling) methodDetails.push(`Sampling: ${methods.sampling}`);
      if (methods.scaling) methodDetails.push(`Preparation: ${methods.scaling}`);
      if (methods.cluster_selection) methodDetails.push(`Cluster selection: ${methods.cluster_selection}`);
      byId("method-details").replaceChildren(...methodDetails.map(text => node("p", text)));
      status.textContent = `Loaded ${fmt(dataset.records)} analyzed records. Amounts displayed in INR.`;
    } catch (error) {
      if (requestId !== summaryRequest) return;
      status.classList.add("error");
      setText("cohort-status", "The cohort summary could not load. Open Overview to retry.");
      status.textContent = error.name === "AbortError" ? "Preparation took longer than expected. Retry after the dataset import completes." : error.message;
      byId("research-retry").hidden = false;
      ["cluster-chart", "topic-list", "loan-structures", "correlation-list", "sentiment-comparison", "region-comparison"].forEach(id => empty(byId(id), "Summary unavailable. Use Retry summary above to load these results."));
    } finally {
      if (requestId === summaryRequest) {
        section.setAttribute("aria-busy", "false");
        summaryController = null;
      }
    }
  }

  let page = 1;
  let pages = 1;
  let recordRequest = 0;
  let recordController = null;
  let borrowersInitialized = false;
  let borrowersNeedRefresh = false;
  async function loadBorrowers() {
    borrowersInitialized = true;
    borrowersNeedRefresh = false;
    const requestId = ++recordRequest;
    if (recordController) recordController.abort();
    const controller = new AbortController();
    recordController = controller;
    const status = byId("borrower-status");
    byId("borrowers").setAttribute("aria-busy", "true");
    byId("previous-page").disabled = true;
    byId("next-page").disabled = true;
    byId("borrowers-retry").hidden = true;
    status.classList.remove("error");
    status.textContent = "Loading borrower records…";
    const params = new URLSearchParams({page: String(page), page_size: "20"});
    const cluster = byId("cluster-filter").value;
    const source = byId("source-filter").value;
    params.set("source", source);
    if (source === "research" && cluster !== "") params.set("cluster", cluster);
    if (purposeFilter) params.set("purpose", purposeFilter);
    try {
      const data = await getJSON(`/api/research/borrowers?${params}`, controller);
      if (requestId !== recordRequest) return;
      const rows = data.items || [];
      const body = byId("borrower-rows");
      body.replaceChildren();
      rows.forEach(item => {
        const row = node("tr");
        const amount = inr(item.loan_amount);
        const sentiment = typeof item.sentiment === "object" ? item.sentiment?.label : item.sentiment;
        [item.borrower_id, human(item.category), amount, item.repayment_status, sentiment, item.cluster_label].forEach((value, index) => {
          const cell = node("td");
          if (index === 3 || index === 4) {
            const label = String(value ?? "Not available");
            const style = /charged|negative|default/i.test(label) ? "negative" : /current|neutral|late|unavailable|not available/i.test(label) ? "neutral" : "";
            cell.append(node("span", label, `status-pill ${style}`));
          } else if (index === 0) {
            if (item.application_id) {
              const link = node("a", String(value).slice(0, 12) + "…");
              link.href = `/applications/${encodeURIComponent(item.application_id)}`;
              cell.append(link);
            } else cell.append(node("span", value ?? "—"));
            cell.append(node("small", item.source_type === "local_application" || item.application_id ? "My application" : "Research record", "record-source"));
          } else cell.textContent = String(value ?? "—");
          row.append(cell);
        });
        body.append(row);
      });
      if (!rows.length) {
        const row = node("tr");
        const cell = node("td", "No records match this borrower group.", "empty-state");
        cell.colSpan = 6;
        row.append(cell);
        body.append(row);
      }
      page = Number(data.page) || 1;
      pages = Number(data.pages) || Math.max(1, Math.ceil((Number(data.total) || 0) / 20));
      setText("page-label", `Page ${page} of ${pages} · ${fmt(data.total)} records`);
      byId("previous-page").disabled = page <= 1;
      byId("next-page").disabled = page >= pages;
      status.textContent = rows.length ? `Showing ${rows.length} ${source === "applications" ? "saved applications" : "research records"}${purposeFilter ? ` · ${human(purposeFilter)}` : ""}${cluster && source === "research" ? " · selected group" : ""}.` : "No matching records.";
    } catch (error) {
      if (requestId !== recordRequest) return;
      status.classList.add("error");
      status.textContent = error.name === "AbortError" ? "The data request timed out. Please retry." : error.message;
      byId("borrowers-retry").hidden = false;
      const row = node("tr");
      const cell = node("td", "Records could not be loaded. Use Retry records above.", "empty-state");
      cell.colSpan = 6;
      row.append(cell);
      byId("borrower-rows").replaceChildren(row);
    } finally {
      if (requestId === recordRequest) {
        byId("borrowers").setAttribute("aria-busy", "false");
        recordController = null;
      }
    }
  }
  function applyPurpose(requested, updateURL = false) {
    const next = knownPurposes.includes(requested) ? requested : "";
    const changed = purposeFilter !== next || requestedPurpose !== requested;
    requestedPurpose = requested;
    purposeFilter = next;
    byId("purpose-filter").value = purposeFilter;
    if (updateURL) {
      const url = new URL(location.href);
      // Keep application_id and other context intact. Explicit empty purpose
      // distinguishes All purposes from an application's default cohort.
      url.searchParams.set("purpose", purposeFilter);
      history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
    if (!changed) return;
    page = 1;
    byId("cluster-filter").value = "";
    setText("cohort-status", "Loading the selected research cohort…");
    loadSummary();
    // Invalidate even hidden requests: an old cohort must never repopulate the
    // records after a history/filter change. Lazy loading stays lazy.
    recordRequest++;
    if (recordController) recordController.abort();
    recordController = null;
    byId("borrowers").setAttribute("aria-busy", "false");
    borrowersNeedRefresh = true;
    if (!byId("borrowers").hidden) loadBorrowers();
  }
  byId("purpose-filter").addEventListener("change", () => applyPurpose(byId("purpose-filter").value, true));
  window.addEventListener("popstate", () => applyPurpose(purposeFromURL()));
  byId("main").addEventListener("atlas:tab", event => {
    if (event.detail.id === "borrowers" && borrowersInitialized && borrowersNeedRefresh) loadBorrowers();
  });
  byId("research-retry").addEventListener("click", loadSummary);
  byId("borrowers-retry").addEventListener("click", loadBorrowers);
  byId("cluster-filter").addEventListener("change", () => { page = 1; loadBorrowers(); });
  byId("source-filter").addEventListener("change", () => {
    page = 1;
    const ownApplications = byId("source-filter").value === "applications";
    byId("cluster-filter").disabled = ownApplications;
    setText("borrower-scope", ownApplications ? "Your saved applications and recorded repayment states. These are separate from observed outcomes in the research corpus." : "Anonymized research records, loaded one page at a time. Amounts are displayed in INR using the documented reference conversion.");
    loadBorrowers();
  });
  byId("previous-page").addEventListener("click", () => { if (page > 1) { page--; loadBorrowers(); } });
  byId("next-page").addEventListener("click", () => { if (page < pages) { page++; loadBorrowers(); } });

  let businessPage = 1;
  let businessPages = 1;
  let businessRequest = 0;
  let businessFiltersTouched = false;
  const businessForm = byId("business-filter-form");
  async function loadBusiness() {
    const requestId = ++businessRequest;
    const status = byId("business-status");
    byId("business-data").setAttribute("aria-busy", "true");
    byId("business-previous").disabled = true;
    byId("business-next").disabled = true;
    byId("business-retry").hidden = true;
    status.textContent = "Loading source records…";
    const params = new URLSearchParams({source: byId("business-source").value, page: String(businessPage), page_size: "20"});
    if (byId("business-product").value.trim()) params.set("product", byId("business-product").value.trim());
    if (byId("business-location").value.trim()) params.set("location", byId("business-location").value.trim());
    try {
      const data = await getJSON(`/api/research/business?${params}`);
      if (requestId !== businessRequest) return;
      setText("business-source-note", data.note || "");
      const columns = data.columns || [];
      const head = node("tr");
      columns.forEach(column => { const th = node("th", column.label); th.scope = "col"; head.append(th); });
      byId("business-columns").replaceChildren(head);
      const body = byId("business-rows");
      body.replaceChildren();
      (data.items || []).forEach(item => {
        const row = node("tr");
        columns.forEach(column => {
          const value = item[column.key];
          const display = value === null || value === undefined || value === "" ? "Not provided" : column.kind === "money" ? inr(value) : column.kind === "number" ? fmt(value) : String(value);
          row.append(node("td", display));
        });
        body.append(row);
      });
      if (!(data.items || []).length) {
        const row = node("tr");
        const cell = node("td", "No source records match these exact filters. Clear the product or location to broaden the view.", "empty-state");
        cell.colSpan = Math.max(columns.length, 1);
        row.append(cell);
        body.append(row);
      }
      businessPage = Number(data.page) || 1;
      businessPages = Math.max(1, Number(data.pages) || 1);
      setText("business-page-label", `Page ${businessPage} of ${businessPages} · ${fmt(data.total)} source records`);
      byId("business-previous").disabled = businessPage <= 1;
      byId("business-next").disabled = businessPage >= businessPages;
      status.textContent = `${(data.items || []).length} records shown · ${byId("business-source").selectedOptions[0].textContent}. Monetary values are in INR.`;
    } catch (error) {
      if (requestId !== businessRequest) return;
      status.textContent = error.name === "AbortError" ? "The source request timed out. Please retry." : error.message;
      byId("business-retry").hidden = false;
    } finally {
      if (requestId === businessRequest) byId("business-data").setAttribute("aria-busy", "false");
    }
  }
  businessForm.addEventListener("input", () => { businessFiltersTouched = true; });
  businessForm.addEventListener("submit", event => { event.preventDefault(); businessFiltersTouched = true; businessPage = 1; loadBusiness(); });
  byId("business-retry").addEventListener("click", loadBusiness);
  byId("business-previous").addEventListener("click", () => { if (businessPage > 1) { businessPage--; loadBusiness(); } });
  byId("business-next").addEventListener("click", () => { if (businessPage < businessPages) { businessPage++; loadBusiness(); } });

  let impactLoading = false;
  async function loadImpact() {
    if (impactLoading) return;
    impactLoading = true;
    byId("household-impact").setAttribute("aria-busy", "true");
    byId("impact-retry").hidden = true;
    byId("impact-status").textContent = "Checking for linked household outcomes…";
    try {
      const data = await getJSON("/api/research/impact");
      setText("impact-status", data.message || "Household outcome data is not available.");
      setText("impact-badge", data.status === "ready" ? "Observed paired changes" : data.status === "validation_error" ? "Data needs correction" : "Awaiting household data");
      const container = byId("impact-groups");
      container.replaceChildren();
      (data.currency_groups || []).forEach(group => {
        const card = node("article", undefined, "impact-group");
        card.append(node("h3", `${group.currency} · ${fmt(group.record_count)} household records`));
        const values = node("div", undefined, "impact-values");
        [["Household income change", group.household_income], ["Per-capita income change", group.per_capita_household_income], ["Business income change", group.business_income]].forEach(([label, metric]) => {
          if (!metric) return;
          const block = node("div");
          block.append(node("span", label), node("strong", number(metric.mean_change) ? `${fmt(metric.mean_change)} ${group.currency}` : "Not measured"), node("small", `Mean monthly change · ${fmt(metric.paired_n)} complete pairs`));
          values.append(block);
        });
        card.append(values);
        if (group.repayment) card.append(node("p", `Paid-on-time installment ratio: ${percent(group.repayment.on_time_ratio)} · ${fmt(group.repayment.installments_due)} installments due.`));
        if (group.followup_days) card.append(node("p", `Median follow-up: ${fmt(group.followup_days.median)} days. Source-currency cohorts remain separate.`));
        if (group.conversion_note) card.append(node("p", group.conversion_note, "small-note"));
        if (group.source_currency && group.source_currency !== "INR") card.append(node("p", `Source currency: ${group.source_currency}. Public amounts are INR display values where a configured rate exists.`, "small-note"));
        container.append(card);
      });
      if (data.data_quality && data.status === "ready") container.append(node("p", `${fmt(data.data_quality.complete_household_pairs)} complete household-income pairs; ${fmt(data.data_quality.incomplete_household_pairs)} incomplete pairs. Each measure uses available paired observations.`, "small-note"));
      if (data.status === "validation_error") {
        const errors = node("ul", undefined, "limitations-list");
        (data.errors || []).forEach(error => errors.append(node("li", `${error.row ? `Row ${error.row}: ` : ""}${error.message}`)));
        container.append(errors);
      }
    } catch (error) {
      setText("impact-status", error.name === "AbortError" ? "The outcome request timed out. Please retry." : error.message);
      byId("impact-retry").hidden = false;
    } finally {
      impactLoading = false;
      byId("household-impact").setAttribute("aria-busy", "false");
    }
  }
  byId("impact-retry").addEventListener("click", loadImpact);

  function whenVisible(element, callback) {
    if (!("IntersectionObserver" in window)) return callback();
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        observer.disconnect();
        callback();
      }
    }, {rootMargin: "100px"});
    observer.observe(element);
  }
  async function loadApplicationContext() {
    const applicationId = pageQuery.get("application_id");
    if (!applicationId) return;
    const container = byId("application-research-context");
    container.hidden = false;
    container.replaceChildren(node("p", "Loading the evidence linked to your application…"));
    try {
      const data = await getJSON(`/api/research/context?application_id=${encodeURIComponent(applicationId)}`);
      container.replaceChildren();
      if (!businessFiltersTouched && data.category) {
        const sector = data.category.sector;
        if (sector === "dairy" || sector === "farm") {
          byId("business-source").value = sector === "farm" ? "farm" : "dairy";
          const context = (data.application_context || []).find(item => item.product && item.product !== data.category.purpose);
          const product = data.category.product || context?.product;
          if (product) byId("business-product").value = product;
          if (!byId("business-data").hidden) loadBusiness();
        }
      }
      const heading = node("div", undefined, "context-heading");
      heading.append(node("strong", `In context: ${data.category?.label || human(purposeFilter)}`), node("span", "Application-specific evidence", "method-pill"));
      container.append(heading, node("p", "The selected research cohort controls portfolio counts, topics, and observed outcomes. Clustering metrics describe the global fitted model. Your own application remains a separate saved record."));
      (data.application_context || []).forEach(context => container.append(node("p", `${context.source}: ${context.description}`, "small-note")));
      if (data.explanation_url) {
        const url = new URL(data.explanation_url, location.origin);
        if (url.origin === location.origin && /^\/applications\/[a-zA-Z0-9-]+\/explanation$/.test(url.pathname)) {
          const link = node("a", "Understand this application's assessment ↗", "text-link");
          link.href = url.pathname;
          link.target = "_blank";
          link.rel = "noopener";
          container.append(link);
        }
      }
    } catch (error) { container.replaceChildren(node("p", error.message)); }
  }
  whenVisible(byId("main"), loadSummary);
  loadApplicationContext();
  whenVisible(byId("borrowers"), loadBorrowers);
  whenVisible(byId("household-impact"), loadImpact);
  whenVisible(byId("business-data"), loadBusiness);
})();
