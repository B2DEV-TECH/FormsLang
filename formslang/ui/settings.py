"""The provider/model settings sheet -- split out of formslang/ui.py."""

from __future__ import annotations

SETTINGS_JS = r"""async function openSettings() {
  let list, cfg;
  try {
    [list, cfg] = await Promise.all([api("/api/providers"), api("/api/settings")]);
    list = list.providers;
  } catch (e) { toast(e.message, true); return; }

  openModal("Settings — which model converts");
  $("modal-path").textContent = "saved to " + cfg.config_path + " — never inside your project";
  $("modal-hint").textContent =
    "CLI providers drive an agent you already pay for — no API key. " +
    "API providers take a key; it is stored on this machine only and never shown again.";

  let chosen = list.find((p) => p.id === cfg.provider) || list[0];

  const row = (p) => {
    const on = p.id === chosen.id;
    const tag = p.blocked
      ? "blocked · enterprise mode"
      : p.kind === "cli"
      ? (p.available ? "cli · your subscription" : "cli · not installed")
      : (p.needs_key ? (p.available ? "api key" : "api key · none yet") : "local");
    return `<div class="entry ${on ? "on" : ""}${p.blocked ? " off" : ""}" data-p="${esc(p.id)}">` +
      `<span class="icon">${on ? "●" : "○"}</span>` +
      `<span class="name">${esc(p.label)}</span><span class="tag">${esc(tag)}</span></div>`;
  };

  /* The per-provider form: only the fields this provider actually needs. */
  const form = (p) => {
    const bits = [];
    if (p.blocked) {
      bits.push(`<div class="keyline warn"><i>&#9888;</i><span>${esc(p.hint || "")}</span></div>`);
    }
    if (p.needs_key) {
      const store = cfg.secure_storage || {};
      const vault = store.label || "the OS credential store";
      const sealed = store.available || cfg.key_source === "env";
      bits.push(`<label>API key
        <input type="password" data-f="api_key" spellcheck="false" autocomplete="off" ${sealed ? "" : "disabled"}
               placeholder="${cfg.has_key ? "saved — leave blank to keep it" : "paste your API key"}"></label>`);
      const src = cfg.key_source === "env" ? "from the environment — wins over anything saved here"
                : cfg.key_source === "keychain" ? `saved in ${vault}`
                : cfg.key_source === "file" ? "in the old config file — save it again to move it into " + vault
                : "not set yet";
      bits.push(`<div class="keyline"><i>${cfg.has_key ? "&#10003;" : "&#9702;"}</i><span>Key: ${esc(src)}</span>` +
        (cfg.key_source === "keychain" || cfg.key_source === "file"
          ? `<button type="button" class="forget" data-forget>forget saved key</button>` : "") +
        `</div>`);
      if (!sealed)
        bits.push(`<div class="keyline warn"><i>&#9888;</i><span>${esc(store.message || "")}</span></div>`);
    }
    if (p.kind === "http" && p.id !== "echo" && p.id !== "azure_openai") {
      bits.push(`<label>Endpoint override (optional)
        <input data-f="base_url" spellcheck="false" value="${esc(cfg.base_url || "")}" placeholder="blank = the provider's default endpoint"></label>`);
    }
    if (p.id === "azure_openai") {
      bits.push(`<label>Endpoint
        <input data-f="base_url" spellcheck="false" value="${esc(cfg.base_url || "")}" placeholder="your Azure OpenAI resource endpoint"></label>`);
      bits.push(`<div class="duo">
        <label>Deployment<input data-f="deployment" spellcheck="false" value="${esc(cfg.deployment || "")}"></label>
        <label>API version<input data-f="api_version" spellcheck="false" value="${esc(cfg.api_version || "")}"></label>
      </div>`);
    }
    if (p.kind === "cli" && !p.blocked) {
      bits.push(`<div class="keyline"><i>${p.available ? "&#10003;" : "&#10007;"}</i>` +
        `<span>${p.available ? "CLI installed — it signs in with your subscription." : esc(p.hint || "Not installed on this machine.")}</span>` +
        (p.available ? `<button type="button" class="btn" data-term>Open setup terminal</button>` : "") +
        `</div>`);
    }
    bits.push(`<div class="testrow"><button type="button" class="btn" data-test>Test</button><span class="out" data-testout></span></div>`);
    return `<div class="settings-form">${bits.join("")}</div>`;
  };

  /* SQLcl path: independent of which AI provider is chosen, so it is its
     own always-visible section rather than part of form(p). */
  const sqlclSection = () => {
    const found = cfg.sqlcl_found;
    const status = cfg.sqlcl_env_override
      ? `<i>&#10003;</i><span>Using ${esc(cfg.sqlcl_path ? "the saved path" : "FORMSLANG_SQLCL_PATH")} — the environment variable wins over this field.</span>`
      : found
      ? `<i>&#10003;</i><span>SQLcl found${cfg.sqlcl_path ? "" : " on PATH"}.</span>`
      : `<i>&#9888;</i><span>SQLcl not found yet — needed to import an export straight into APEX.</span>`;
    return `<div class="settings-form">
      <label>SQLcl path (sql / sql.exe)
        <input data-f="sqlcl_path" spellcheck="false" autocomplete="off"
               value="${esc(cfg.sqlcl_path || "")}"
               placeholder="blank = look on PATH, e.g. C:\\sqlcl\\bin\\sql.exe" ${cfg.sqlcl_env_override ? "disabled" : ""}></label>
      <div class="keyline${found ? "" : " warn"}">${status}</div>
    </div>`;
  };

  const render = () => {
    const body = $("modal-body");
    body.innerHTML = list.map(row).join("") + form(chosen) + sqlclSection();
    body.querySelectorAll(".entry[data-p]").forEach((e) => (e.onclick = () => {
      chosen = list.find((p) => p.id === e.dataset.p);
      render();
    }));

    const field = (name) => {
      const el = body.querySelector(`[data-f="${name}"]`);
      return el ? el.value.trim() : "";
    };
    /* What travels on save/test: the provider, the model, and only the
       fields this provider's form actually shows. An untouched key field
       stays out of the payload, so a stored key is kept, not clobbered. */
    const payload = () => {
      const out = { provider: chosen.id, model: $("modal-input").value.trim() };
      for (const name of ["base_url", "deployment", "api_version"])
        if (body.querySelector(`[data-f="${name}"]`)) out[name] = field(name);
      if (field("api_key")) out.api_key = field("api_key");
      if (!cfg.sqlcl_env_override) out.sqlcl_path = field("sqlcl_path");
      return out;
    };

    const testBtn = body.querySelector("[data-test]");
    const testOut = body.querySelector("[data-testout]");
    testBtn.onclick = async () => {
      testOut.className = "out";
      testOut.innerHTML = `<span class="spin"></span> asking the model for one word…`;
      testBtn.disabled = true;
      try {
        const r = await api("/api/settings/test", payload());
        testOut.className = "out " + (r.ok ? "ok" : "bad");
        testOut.textContent = (r.ok ? "✓ answered — " : "✗ ") + r.message;
      } catch (e) {
        testOut.className = "out bad";
        testOut.textContent = "✗ " + e.message;
      }
      testBtn.disabled = false;
    };

    const term = body.querySelector("[data-term]");
    if (term) term.onclick = async () => {
      try {
        await api("/api/terminal", { provider: chosen.id });
        toast("Terminal opened — sign in there, then press Test.");
      } catch (e) { toast(e.message, true); }
    };

    const forget = body.querySelector("[data-forget]");
    if (forget) forget.onclick = async () => {
      try {
        cfg = await api("/api/settings", { api_key: "" });
        toast("Key forgotten.");
        render();
      } catch (e) { toast(e.message, true); }
    };

    foot({
      placeholder: `model (blank = ${chosen.default_model || "provider default"})`,
      value: chosen.id === cfg.provider ? cfg.model : chosen.default_model,
      options: chosen.models.length ? chosen.models : (chosen.default_model ? [chosen.default_model] : []),
      button: `Save · use ${chosen.label}`,
      run: async () => {
        try {
          cfg = await api("/api/settings", payload());
          closeModal();
          await refresh();
          toast(`Converting with ${state.provider}.`);
        } catch (e) { toast(e.message, true); }
      },
    });
  };
  render();
}

"""
