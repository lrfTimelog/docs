/**
 * Base-URL builder for the "Set up your site" page.
 *
 * Why this exists: the API Explorer does not render OpenAPI server variables as
 * inputs. It substitutes their defaults into one URL and lets the reader
 * double-click to replace the whole string. That works, and it persists across
 * endpoints — but it is undiscoverable, and the reader still has to assemble the
 * URL themselves from two parts of their own address.
 *
 * So this turns the assembly into two fields. It deliberately does NOT reach into
 * the Explorer: Fern documents built-in components as out of scope for custom JS,
 * and a script driving their internal state would break on any of their deploys.
 * It produces a string to paste. Nothing more.
 *
 * Mounted on <div id="tl-site-setup" />. The docs are a client-side app, so the
 * mount point can arrive after this script runs and can be replaced on
 * navigation — hence the observer rather than a one-shot call.
 */
(function () {
  var MOUNT_ID = "tl-site-setup";

  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "style") el.style.cssText = attrs[k];
      else el.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return el;
  }

  function field(labelText, placeholder, hint) {
    var input = h("input", {
      type: "text",
      placeholder: placeholder,
      spellcheck: "false",
      autocapitalize: "off",
      autocomplete: "off",
      style:
        "width:100%;padding:8px 10px;border:1px solid var(--grayscale-a5,#8883);" +
        "border-radius:6px;background:transparent;color:inherit;font:inherit;",
    });
    var wrap = h("label", { style: "display:block;flex:1 1 180px;min-width:0;" }, [
      h("span", { style: "display:block;font-size:.8rem;opacity:.75;margin-bottom:4px;" }, [labelText]),
      input,
      h("span", { style: "display:block;font-size:.72rem;opacity:.6;margin-top:4px;" }, [hint]),
    ]);
    return { wrap: wrap, input: input };
  }

  function mount(root) {
    root.textContent = "";

    var instance = field("Instance", "3", "The number in app3.timelog.com");
    var account = field("Account", "acme", "The segment after the host");

    var out = h("code", {
      style:
        "flex:1 1 auto;padding:10px 12px;border-radius:6px;background:var(--grayscale-a3,#8882);" +
        "font-size:.85rem;overflow-x:auto;white-space:nowrap;",
    });
    var copy = h("button", {
      type: "button",
      style:
        "padding:9px 14px;border-radius:6px;border:1px solid var(--grayscale-a5,#8883);" +
        "background:transparent;color:inherit;font:inherit;cursor:pointer;white-space:nowrap;",
    });
    copy.textContent = "Copy";

    function url() {
      var i = instance.input.value.trim().replace(/^app/i, "");
      var a = account.input.value.trim().replace(/^\/+|\/+$/g, "");
      if (!i || !a) return null;
      return "https://app" + i + ".timelog.com/" + a + "/api";
    }

    function refresh() {
      var u = url();
      out.textContent = u || "Fill both fields to build your base URL";
      out.style.opacity = u ? "1" : ".55";
      copy.disabled = !u;
      copy.style.opacity = u ? "1" : ".45";
      copy.style.cursor = u ? "pointer" : "not-allowed";
      copy.textContent = "Copy";
    }

    copy.addEventListener("click", function () {
      var u = url();
      if (!u) return;
      // Clipboard API is unavailable on insecure origins and in some embeds;
      // failing silently would look like a broken button.
      var done = function (ok) {
        copy.textContent = ok ? "Copied" : "Press Ctrl+C";
        if (!ok) window.getSelection().selectAllChildren(out);
        setTimeout(refresh, 1600);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(u).then(
          function () { done(true); },
          function () { done(false); }
        );
      } else {
        done(false);
      }
    });

    [instance.input, account.input].forEach(function (el) {
      el.addEventListener("input", refresh);
    });

    root.appendChild(
      h("div", { style: "display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px;" }, [
        instance.wrap,
        account.wrap,
      ])
    );
    root.appendChild(
      h("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap;" }, [out, copy])
    );

    refresh();
    root.dataset.tlMounted = "1";
  }

  function scan() {
    var root = document.getElementById(MOUNT_ID);
    if (root && !root.dataset.tlMounted) mount(root);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scan);
  } else {
    scan();
  }
  new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
})();
