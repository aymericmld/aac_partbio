/* Page de restitution : lit data/site.json et data/aac.geojson produits par
   `python -m aac_partbio exporter`. Aucune donnée n'est écrite en dur ici. */
(async function () {
  "use strict";

  const fmtInt = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  const fmt1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
  const pct = (v, d = 1) => (v == null ? "–" : `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }).format(v * 100)} %`);
  const ha = (v) => (v == null ? "–" : `${fmtInt.format(v)} ha`);
  const pts = (v) => (v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${fmt1.format(Math.abs(v * 100))} pt`);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const $ = (id) => document.getElementById(id);

  // Classes de part bio (seuils) et rampe verte validée (un seul ton, clair -> foncé).
  const SEUILS = [0.05, 0.1, 0.2, 0.35];
  const RAMPE = ["#7ab862", "#56a145", "#348a3c", "#1f6d30", "#0f4d22"];
  const SANS_SAU = "#e4e1d8";
  const SAU_MIN = 10; // ha : en dessous, la part bio est jugée fragile
  const classe = (p) => SEUILS.findIndex((s) => p < s) === -1 ? SEUILS.length : SEUILS.findIndex((s) => p < s);
  const couleur = (p) => (p == null ? SANS_SAU : RAMPE[classe(p)]);

  let site, aac;
  try {
    [site, aac] = await Promise.all([
      fetch("data/site.json").then((r) => r.json()),
      fetch("data/aac.geojson").then((r) => r.json()),
    ]);
  } catch (e) {
    document.querySelector("main").insertAdjacentHTML("afterbegin",
      `<p class="demo-banner">Données introuvables : lancez <code>python -m aac_partbio exporter</code> puis servez le dossier docs/ (par exemple <code>python -m http.server -d docs</code>).</p>`);
    return;
  }

  const meta = site.meta;
  const annee = meta.derniere;
  const prec = meta.precedente;
  const nat = site.nationale[annee];
  const natPrec = prec ? site.nationale[prec] : null;
  const features = aac.features;
  const parCode = new Map(features.map((f) => [f.properties.cdaac, f]));

  // ---------------------------------------------------------------- en-tête
  $("demo-banner").hidden = !meta.demo;
  $("kpi-aac").textContent = fmtInt.format(nat.nb_aac);
  const sau = nat.sau_aac_ha;
  $("kpi-sau").innerHTML = sau >= 1e6 ? `${fmt1.format(sau / 1e6)}<small>M ha</small>` : sau >= 1e4 ? `${fmtInt.format(sau / 1e3)}<small>k ha</small>` : `${fmtInt.format(sau)}<small>ha</small>`;
  $("kpi-bio").innerHTML = `${fmt1.format(nat.part_bio_aac * 100)}<small>%</small>`;
  if (nat.part_bio_pac_aac != null && nat.part_bio_pac_france != null) {
    $("compare-line").innerHTML = `À base égale, sur les seules parcelles constatées bio dans le RPG ${annee} :
      <b>${pct(nat.part_bio_pac_aac)}</b> de la surface des parcelles qui touchent une AAC, contre
      <b>${pct(nat.part_bio_pac_france)}</b> sur l'ensemble du RPG chargé. CartoBio ajoute les parcelles bio hors PAC.`;
  } else {
    $("compare-line").textContent = `Millésime ${annee} du RPG et des parcelles bio, sur ${fmtInt.format(nat.nb_parcelles_aac)} parcelles.`;
  }
  $("pill-rpg").textContent = `millésime ${annee}`;
  $("pill-bio").textContent = `millésime ${annee}`;
  $("m-buffer").textContent = meta.buffer_m;
  $("m-seuil").textContent = pct(meta.seuil_recouvrement, 0);
  $("src-rpg").href = meta.sources.rpg;
  $("src-bio").href = meta.sources.bio;
  $("src-aac").href = meta.sources.aac;
  $("footer-date").textContent = `Données générées le ${new Date(meta.genere_le).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}${meta.demo ? " (démonstration)" : ""}.`;

  const q = site.qualite[annee] || {};
  $("quality").innerHTML = [
    [pct(q.taux_appariement_bio, 0), "des parcelles bio retrouvées dans le RPG"],
    [pct(q.concordance_categories, 0), "de catégories identiques entre les deux sources"],
    [pct(q.part_chevauchement_residuel, 2), "de surface en chevauchement résiduel"],
  ].map(([v, l]) => `<div><b>${v}</b><span>${l}</span></div>`).join("");

  // --------------------------------------------------------------- tooltip
  const tip = $("tooltip");
  const showTip = (html, ev) => {
    tip.innerHTML = html;
    tip.classList.add("show");
    const x = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 10);
    tip.style.left = `${x}px`;
    tip.style.top = `${ev.clientY + 14}px`;
  };
  const hideTip = () => tip.classList.remove("show");

  // ----------------------------------------------------- barres empilées
  function barres(cible, lignes, mode, compact = false) {
    const max = Math.max(...lignes.map((l) => l.sau_ha), 1);
    cible.innerHTML = lignes.map((l) => {
      const bio = l.sau_bio_ha || 0, conv = Math.max(l.sau_ha - bio, 0);
      const part = l.sau_ha ? bio / l.sau_ha : 0;
      const echelle = mode === "part" ? 100 / (l.sau_ha || 1) : 100 / max;
      const segs = [
        bio > 0 ? `<div class="seg bio" style="width:${bio * echelle}%"></div>` : "",
        conv > 0 ? `<div class="seg conv" style="width:${conv * echelle}%"></div>` : "",
      ].join("");
      const val = mode === "part" ? pct(part, compact ? 0 : 1) : compact ? fmtInt.format(l.sau_ha) : ha(l.sau_ha);
      return `<div class="bar-row" data-nom="${esc(l.categorie)}" data-sau="${l.sau_ha}" data-bio="${bio}">
        <div class="name">${esc(l.categorie)}</div><div class="bar-track">${segs}</div><div class="val">${val}</div></div>`;
    }).join("");
    cible.querySelectorAll(".bar-row").forEach((row) => {
      row.addEventListener("mousemove", (ev) => {
        const s = +row.dataset.sau, b = +row.dataset.bio;
        showTip(`<b>${esc(row.dataset.nom)}</b><br>Surface : ${ha(s)}<br>Bio et conversion : ${ha(b)} (${pct(s ? b / s : 0)})<br>Conventionnel : ${ha(s - b)}`, ev);
      });
      row.addEventListener("mouseleave", hideTip);
    });
  }

  const categories = [...(site.categories[annee] || [])].sort((a, b) => b.sau_ha - a.sau_ha);
  let modeCultures = "ha";
  function dessinerCultures() {
    const tableau = modeCultures === "table";
    $("bars").hidden = tableau;
    $("cat-table").hidden = !tableau;
    $("cultures-titre").textContent = modeCultures === "part" ? "Part du bio dans chaque catégorie" : "Surface agricole par catégorie";
    if (tableau) {
      $("cat-table").innerHTML = `<table><thead><tr><th>Catégorie</th><th class="r">Surface (ha)</th><th class="r">Bio (ha)</th><th class="r">dont conversion</th><th class="r">Part bio</th></tr></thead><tbody>${
        categories.map((c) => `<tr><td>${esc(c.categorie)}</td><td class="r">${fmtInt.format(c.sau_ha)}</td><td class="r">${fmtInt.format(c.sau_bio_ha)}</td><td class="r">${fmtInt.format(c.sau_conversion_ha)}</td><td class="r">${pct(c.part_bio)}</td></tr>`).join("")}</tbody></table>`;
    } else {
      const lignes = modeCultures === "part" ? [...categories].sort((a, b) => b.part_bio - a.part_bio) : categories;
      barres($("bars"), lignes, modeCultures);
    }
  }
  document.querySelectorAll(".seg-toggle button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".seg-toggle button").forEach((x) => x.classList.toggle("on", x === b));
    modeCultures = b.dataset.mode;
    dessinerCultures();
  }));
  dessinerCultures();

  const classees = categories.filter((c) => c.categorie !== "Non classé");
  if (classees.length) {
    const top = classees[0];
    const plusBio = [...classees].filter((c) => c.sau_ha > 0.02 * sau).sort((a, b) => b.part_bio - a.part_bio)[0];
    $("cultures-texte").innerHTML = `<b>${esc(top.categorie)}</b> occupent ${pct(top.sau_ha / sau, 0)} de la surface agricole des AAC.
      Parmi les catégories qui pèsent au moins 2 % de la surface, la plus engagée en bio est
      <b>${esc(plusBio.categorie.toLowerCase())}</b>, avec ${pct(plusBio.part_bio, 0)} de surfaces bio ou en conversion.`;
  }

  // -------------------------------------------------------------- carte
  const map = L.map("map", { zoomControl: true, scrollWheelZoom: false, preferCanvas: true }).setView([46.6, 2.4], 6);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: "© OpenStreetMap, © CARTO", subdomains: "abcd", maxZoom: 18,
  }).addTo(map);
  map.on("focus", () => map.scrollWheelZoom.enable());
  map.on("blur", () => map.scrollWheelZoom.disable());

  let selection = null;
  const style = (f) => {
    const p = f.properties;
    const vide = !p.sau_ha;
    return {
      color: selection === p.cdaac ? "#12261e" : "#fffefb",
      weight: selection === p.cdaac ? 2.5 : 0.8,
      fillColor: vide ? SANS_SAU : couleur(p.part_bio),
      fillOpacity: 0.85,
    };
  };
  let filtre = "";
  const couche = L.geoJSON(aac, {
    style,
    filter: () => true,
    onEachFeature: (f, layer) => {
      const p = f.properties;
      layer.bindTooltip(`<b>${esc(p.nom || p.cdaac)}</b><br>${p.sau_ha ? `${pct(p.part_bio)} de bio · ${ha(p.sau_ha)}` : "Pas de surface agricole connue"}`, { className: "aac-tip", sticky: true });
      layer.on("click", () => choisir(p.cdaac, false));
    },
  }).addTo(map);
  if (features.length) map.fitBounds(couche.getBounds(), { padding: [20, 20] });

  // Légende : classes de la rampe + absence de surface agricole.
  const bornes = [0, ...SEUILS];
  $("legend").innerHTML = `<b>Part bio de la surface agricole</b>${RAMPE.map((c, i) =>
    `<div class="row"><span class="sw" style="background:${c}"></span>${i < SEUILS.length ? `${bornes[i] * 100} à ${SEUILS[i] * 100} %` : `${SEUILS.at(-1) * 100} % et plus`}</div>`).join("")}
    <div class="row"><span class="sw nodata"></span>Sans surface agricole</div>`;

  // Filtre par catégorie dominante.
  const dominantes = [...new Set(features.map((f) => f.properties.categorie_dominante).filter(Boolean))].sort();
  $("filtre-cat").insertAdjacentHTML("beforeend", dominantes.map((c) => `<option>${esc(c)}</option>`).join(""));
  $("filtre-cat").addEventListener("change", (e) => {
    filtre = e.target.value;
    couche.eachLayer((l) => {
      const ok = !filtre || l.feature.properties.categorie_dominante === filtre;
      l.setStyle(ok ? style(l.feature) : { fillOpacity: 0.06, opacity: 0.2 });
    });
    majCompteur();
    tableau.page = 0;
    dessinerTableau();
  });
  const majCompteur = () => {
    const n = features.filter((f) => !filtre || f.properties.categorie_dominante === filtre).length;
    $("map-count").textContent = `${fmtInt.format(n)} AAC affichées`;
  };
  majCompteur();

  // Recherche.
  $("aac-list").innerHTML = features.map((f) => `<option value="${esc(f.properties.nom || "")} · ${esc(f.properties.cdaac)}">`).join("");
  $("search").addEventListener("change", (e) => {
    const code = e.target.value.split("·").pop().trim();
    const trouve = parCode.get(code) || features.find((f) => (f.properties.nom || "").toLowerCase() === e.target.value.trim().toLowerCase());
    if (trouve) choisir(trouve.properties.cdaac, true);
  });

  function choisir(code, zoom) {
    selection = code;
    let cible = null;
    couche.eachLayer((l) => {
      const ok = !filtre || l.feature.properties.categorie_dominante === filtre;
      l.setStyle(ok ? style(l.feature) : { fillOpacity: 0.06, opacity: 0.2 });
      if (l.feature.properties.cdaac === code) cible = l;
    });
    if (cible) {
      cible.bringToFront();
      if (zoom) map.fitBounds(cible.getBounds(), { maxZoom: 12, padding: [40, 40] });
    }
    panneau(parCode.get(code).properties);
  }

  function panneau(p) {
    const lignes = meta.categories
      .filter((c) => p.categories[c])
      .map((c) => ({ categorie: c, sau_ha: p.categories[c][0], sau_bio_ha: p.categories[c][1] }))
      .sort((a, b) => b.sau_ha - a.sau_ha);
    const evo = p.part_bio != null && p.part_bio_prec != null ? p.part_bio - p.part_bio_prec : null;
    $("panel").innerHTML = `
      <div class="code">${esc(p.cdaac)}</div>
      <h3>${esc(p.nom || "AAC sans nom")}</h3>
      ${p.sau_ha && p.sau_ha < SAU_MIN ? `<p class="muted"><i class="fa-solid fa-triangle-exclamation"></i> Moins de ${SAU_MIN} ha agricoles : part bio fragile.</p>` : ""}
      <div class="metrics">
        <div class="metric"><b>${pct(p.part_bio)}</b><span>part bio${evo != null ? ` · <span class="delta ${evo >= 0 ? "up" : "down"}">${pts(evo)} vs ${prec}</span>` : ""}</span></div>
        <div class="metric"><b>${ha(p.sau_ha)}</b><span>surface agricole (${pct(p.part_sau, 0)} de l'AAC)</span></div>
        <div class="metric"><b>${ha(p.sau_ab_ha)}</b><span>certifiés bio (AB)</span></div>
        <div class="metric"><b>${ha(p.sau_conversion_ha)}</b><span>en conversion</span></div>
        <div class="metric"><b>${ha(p.surface_aac_ha)}</b><span>surface de l'AAC</span></div>
        <div class="metric"><b>${fmtInt.format(p.nb_parcelles)}</b><span>parcelles</span></div>
      </div>
      <div class="chart-legend"><span><i style="background:var(--accent)"></i>Bio</span><span><i style="background:var(--conv)"></i>Conventionnel</span><span class="muted">surface, ha</span></div>
      <div class="bars" id="panel-bars"></div>`;
    if (lignes.length) barres($("panel-bars"), lignes, "ha", true);
    else $("panel-bars").innerHTML = `<p class="muted">Aucune parcelle agricole connue dans cette AAC.</p>`;
  }

  // ------------------------------------------------------------ tableau
  const colonnes = [
    ["nom", "AAC", (p) => `${esc(p.nom || "–")}<div class="muted">${esc(p.cdaac)}</div>`],
    ["categorie_dominante", "Culture dominante", (p) => esc(p.categorie_dominante || "–")],
    ["sau_ha", "Surface agricole", (p) => ha(p.sau_ha), "r"],
    ["part_sau", "Part agricole", (p) => pct(p.part_sau, 0), "r"],
    ["part_bio", "Part bio", (p) => `<span class="minibar" style="width:${Math.round((p.part_bio || 0) * 60)}px"></span>${pct(p.part_bio)}${p.sau_ha && p.sau_ha < SAU_MIN ? " *" : ""}`, "r"],
  ];
  if (prec) colonnes.push(["evo", `Évol. vs ${prec}`, (p) => (p.evo == null ? "–" : `<span class="delta ${p.evo >= 0 ? "up" : "down"}">${pts(p.evo)}</span>`), "r"]);
  features.forEach((f) => {
    const p = f.properties;
    p.evo = p.part_bio != null && p.part_bio_prec != null ? p.part_bio - p.part_bio_prec : null;
  });
  const tableau = { tri: "sau_ha", asc: false, page: 0, taille: 15 };
  function dessinerTableau() {
    const lignes = features.map((f) => f.properties)
      .filter((p) => !filtre || p.categorie_dominante === filtre)
      .sort((a, b) => {
        const va = a[tableau.tri], vb = b[tableau.tri];
        if (va == null) return 1;
        if (vb == null) return -1;
        const r = typeof va === "string" ? va.localeCompare(vb, "fr") : va - vb;
        return tableau.asc ? r : -r;
      });
    const pages = Math.max(1, Math.ceil(lignes.length / tableau.taille));
    tableau.page = Math.min(tableau.page, pages - 1);
    const vue = lignes.slice(tableau.page * tableau.taille, (tableau.page + 1) * tableau.taille);
    $("aac-table").innerHTML = `<thead><tr>${colonnes.map(([k, t, , cl]) =>
      `<th data-k="${k}" class="${cl || ""} ${tableau.tri === k ? `sorted${tableau.asc ? " asc" : ""}` : ""}">${t}</th>`).join("")}</tr></thead>
      <tbody>${vue.map((p) => `<tr data-code="${esc(p.cdaac)}">${colonnes.map(([, , rendu, cl]) => `<td class="${cl || ""}">${rendu(p)}</td>`).join("")}</tr>`).join("")}</tbody>`;
    $("pager").innerHTML = `<span class="muted">${fmtInt.format(lignes.length)} AAC · page ${tableau.page + 1} / ${pages}</span>
      <button id="prev" ${tableau.page === 0 ? "disabled" : ""}>Précédent</button><button id="next" ${tableau.page >= pages - 1 ? "disabled" : ""}>Suivant</button>`;
    $("prev").onclick = () => { tableau.page--; dessinerTableau(); };
    $("next").onclick = () => { tableau.page++; dessinerTableau(); };
    $("aac-table").querySelectorAll("th").forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.k;
      tableau.asc = tableau.tri === k ? !tableau.asc : k === "nom";
      tableau.tri = k;
      dessinerTableau();
    }));
    $("aac-table").querySelectorAll("tbody tr").forEach((tr) => tr.addEventListener("click", () => {
      choisir(tr.dataset.code, true);
      $("carte").scrollIntoView({ behavior: "smooth" });
    }));
  }
  dessinerTableau();

  // ------------------------------------------------------------ évolution
  if (natPrec) {
    $("evolution").hidden = false;
    $("evo-titre").textContent = `Évolution entre ${prec} et ${annee}`;
    const comparables = features.map((f) => f.properties).filter((p) => p.evo != null && p.sau_ha >= SAU_MIN);
    const hausse = comparables.filter((p) => p.evo > 0.001).length;
    const baisse = comparables.filter((p) => p.evo < -0.001).length;
    $("evo-grid").innerHTML = `
      <div class="evo reveal"><span class="kicker">Part bio dans les AAC</span>
        <div class="from-to num">${pct(natPrec.part_bio_aac)}<span class="arrow">→</span>${pct(nat.part_bio_aac)}</div>
        <p class="muted">${pts(nat.part_bio_aac - natPrec.part_bio_aac)} en un an.</p></div>
      <div class="evo reveal"><span class="kicker">Surface bio dans les AAC</span>
        <div class="from-to num">${fmtInt.format(natPrec.sau_bio_aac_ha)}<span class="arrow">→</span>${fmtInt.format(nat.sau_bio_aac_ha)}</div>
        <p class="muted">hectares bio ou en conversion.</p></div>
      <div class="evo reveal"><span class="kicker">AAC où le bio progresse</span>
        <div class="from-to num">${fmtInt.format(hausse)}<span class="arrow">/</span>${fmtInt.format(comparables.length)}</div>
        <p class="muted">${fmtInt.format(baisse)} AAC reculent, parmi celles d'au moins ${SAU_MIN} ha agricoles.</p></div>`;
  }

  // ------------------------------------------------- navigation et révélations
  const sections = [...document.querySelectorAll(".section")].filter((s) => !s.hidden);
  $("dots").innerHTML = sections.map((s) => `<button class="dot" data-id="${s.id}" aria-label="${s.dataset.titre}"><span>${s.dataset.titre}</span></button>`).join("");
  $("dots").querySelectorAll(".dot").forEach((d) => d.addEventListener("click", () => $(d.dataset.id).scrollIntoView({ behavior: "smooth" })));
  const obsSection = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (e.isIntersecting) document.querySelectorAll(".dot").forEach((d) => d.classList.toggle("active", d.dataset.id === e.target.id));
  }), { threshold: 0.35 });
  sections.forEach((s) => obsSection.observe(s));
  const obsReveal = new IntersectionObserver((entries) => entries.forEach((e) => {
    if (e.isIntersecting) { e.target.classList.add("visible"); obsReveal.unobserve(e.target); }
  }), { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach((el) => obsReveal.observe(el));
  setTimeout(() => map.invalidateSize(), 300);
})();
