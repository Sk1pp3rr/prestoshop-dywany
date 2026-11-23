/*
 * Baner zgody na pliki cookies zgodny ze standardami UE (RODO / ePrivacy)
 * dla motywu PrestaShop 8.2 "classic" (/themes/classic/assets/js/custom.js).
 */
(function () {
  "use strict";

  var COOKIE_NAME = "mosquito_cookie_consent";
  var COOKIE_MAX_AGE = 60 * 60 * 24 * 180; // 180 dni

  function readConsent() {
    var match = document.cookie.match(new RegExp("(?:^|; )" + COOKIE_NAME + "=([^;]*)"));
    if (match && match[1]) {
      try {
        return JSON.parse(decodeURIComponent(match[1]));
      } catch (_err) {
        return null;
      }
    }
    return null;
  }

  function saveConsent(consent) {
    var payload = {
      essential: true,
      analytics: Boolean(consent.analytics),
      marketing: Boolean(consent.marketing),
      updatedAt: new Date().toISOString()
    };
    var serialized = JSON.stringify(payload);
    var secureFlag = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie =
      COOKIE_NAME +
      "=" +
      encodeURIComponent(serialized) +
      "; path=/; max-age=" +
      COOKIE_MAX_AGE +
      "; SameSite=Lax" +
      secureFlag;
    window.dispatchEvent(new CustomEvent("cookieConsentUpdated", { detail: payload }));
  }

  function injectStyles() {
    if (document.getElementById("gdpr-cookie-styles")) {
      return;
    }
    var style = document.createElement("style");
    style.id = "gdpr-cookie-styles";
    style.textContent =
      "#gdpr-cookie-banner{position:fixed;left:16px;right:16px;bottom:16px;max-width:760px;margin:0 auto;background:#fff;color:#111;border:1px solid #d9d9d9;box-shadow:0 12px 36px rgba(0,0,0,.16);z-index:9999;padding:20px 22px;font-family:Poppins,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:13px;line-height:1.5}" +
      "#gdpr-cookie-banner h3{margin:0 0 6px;font-size:15px;font-weight:600;color:#111}" +
      "#gdpr-cookie-banner p{margin:0 0 12px;color:#333}" +
      "#gdpr-cookie-banner a{color:#111;text-decoration:underline}" +
      ".gdpr-cookie-options{display:none;border-top:1px solid #e5e5e5;border-bottom:1px solid #e5e5e5;padding:10px 0;margin:10px 0 14px}" +
      ".gdpr-cookie-options.is-open{display:block}" +
      ".gdpr-cookie-opt{display:flex;align-items:flex-start;gap:10px;margin:6px 0;cursor:pointer}" +
      ".gdpr-cookie-opt input{margin-top:3px}" +
      ".gdpr-cookie-opt small{display:block;color:#666;font-size:12px}" +
      ".gdpr-cookie-actions{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end}" +
      ".gdpr-btn{border:1px solid #111;padding:9px 15px;font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;cursor:pointer;background:#fff;color:#111;transition:background .15s,color .15s}" +
      ".gdpr-btn:hover{background:#f2f2f2}" +
      ".gdpr-btn-primary{background:#111;color:#fff}" +
      ".gdpr-btn-primary:hover{background:#333;color:#fff}" +
      ".gdpr-btn-save{display:none}" +
      ".gdpr-cookie-options.is-open + .gdpr-cookie-actions .gdpr-btn-save{display:inline-block}" +
      "#gdpr-cookie-reopen{position:fixed;left:14px;bottom:14px;z-index:9998;background:#111;color:#fff;border:none;padding:6px 11px;font-size:11px;letter-spacing:.04em;text-transform:uppercase;cursor:pointer;opacity:.82}" +
      "#gdpr-cookie-reopen:hover{opacity:1}" +
      "@media(max-width:600px){#gdpr-cookie-banner{left:10px;right:10px;bottom:10px;padding:16px}.gdpr-cookie-actions{flex-direction:column}.gdpr-btn{width:100%}}";
    document.head.appendChild(style);
  }

  function showReopenButton() {
    if (document.getElementById("gdpr-cookie-reopen")) {
      return;
    }
    var btn = document.createElement("button");
    btn.id = "gdpr-cookie-reopen";
    btn.type = "button";
    btn.textContent = "Cookies";
    btn.setAttribute("aria-label", "Zmień ustawienia plików cookies");
    btn.addEventListener("click", function () {
      btn.remove();
      renderBanner(readConsent());
    });
    document.body.appendChild(btn);
  }

  function renderBanner(existing) {
    if (document.getElementById("gdpr-cookie-banner")) {
      return;
    }
    injectStyles();

    var analyticsChecked = existing ? Boolean(existing.analytics) : false;
    var marketingChecked = existing ? Boolean(existing.marketing) : false;

    var banner = document.createElement("div");
    banner.id = "gdpr-cookie-banner";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-modal", "false");
    banner.setAttribute("aria-label", "Informacja o plikach cookies");

    banner.innerHTML =
      '<h3>Dbamy o Twoją prywatność (pliki cookies)</h3>' +
      '<p>Używamy niezbędnych plików cookies do działania sklepu (sesja, koszyk, logowanie) oraz opcjonalnych cookies analitycznych i marketingowych. Możesz zaakceptować wszystkie, wybrać tylko niezbędne albo dostosować ustawienia. Szczegóły znajdziesz w <a href="/pl/content/3-polityka-prywatnosci">Polityce prywatności</a>.</p>' +
      '<div class="gdpr-cookie-options" id="gdpr-cookie-options">' +
      '  <label class="gdpr-cookie-opt"><input type="checkbox" checked disabled /><span><strong>Niezbędne</strong><small>Wymagane do działania koszyka, kasy i bezpieczeństwa (zawsze aktywne).</small></span></label>' +
      '  <label class="gdpr-cookie-opt"><input type="checkbox" id="gdpr-opt-analytics"' + (analyticsChecked ? " checked" : "") + ' /><span><strong>Analityczne</strong><small>Pomagają nam ulepszać działanie sklepu i statystyki odwiedzin.</small></span></label>' +
      '  <label class="gdpr-cookie-opt"><input type="checkbox" id="gdpr-opt-marketing"' + (marketingChecked ? " checked" : "") + ' /><span><strong>Marketingowe</strong><small>Pozwalają dopasować oferty i promocje.</small></span></label>' +
      "</div>" +
      '<div class="gdpr-cookie-actions">' +
      '  <button type="button" class="gdpr-btn" id="gdpr-btn-settings">Ustawienia</button>' +
      '  <button type="button" class="gdpr-btn gdpr-btn-save" id="gdpr-btn-save">Zapisz wybór</button>' +
      '  <button type="button" class="gdpr-btn" id="gdpr-btn-essential">Tylko niezbędne</button>' +
      '  <button type="button" class="gdpr-btn gdpr-btn-primary" id="gdpr-btn-accept">Akceptuj wszystkie</button>' +
      "</div>";

    document.body.appendChild(banner);

    var optionsEl = document.getElementById("gdpr-cookie-options");
    document.getElementById("gdpr-btn-settings").addEventListener("click", function () {
      optionsEl.classList.toggle("is-open");
    });

    function closeWithConsent(consent) {
      saveConsent(consent);
      banner.remove();
      showReopenButton();
    }

    document.getElementById("gdpr-btn-essential").addEventListener("click", function () {
      closeWithConsent({ analytics: false, marketing: false });
    });

    document.getElementById("gdpr-btn-accept").addEventListener("click", function () {
      closeWithConsent({ analytics: true, marketing: true });
    });

    document.getElementById("gdpr-btn-save").addEventListener("click", function () {
      var a = document.getElementById("gdpr-opt-analytics").checked;
      var m = document.getElementById("gdpr-opt-marketing").checked;
      closeWithConsent({ analytics: a, marketing: m });
    });
  }

  function init() {
    var existing = readConsent();
    if (existing && existing.essential) {
      showReopenButton();
    } else {
      renderBanner(null);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
