/* SheMarket — search.js
   Handles: autocomplete (product + seller inputs), price range slider,
            rating picker, category selector, verified toggle */

(function () {
    "use strict";

    // ── Utilities ────────────────────────────────────────────────
    function debounce(fn, ms) {
        let t;
        return function (...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); };
    }
    function qs(sel, ctx)  { return (ctx || document).querySelector(sel); }
    function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

    // ── Autocomplete factory ──────────────────────────────────────
    function initAutocomplete(input, box, filterType) {
        if (!input || !box) return;

        const url = qs("#searchInput")?.dataset.suggestionsUrl
                 || input.dataset.suggestionsUrl;

        const icons = { product: "bi-box-seam", seller: "bi-shop", category: "bi-tag" };

        const fetch_ = debounce(async function (q) {
            if (q.length < 2) { hide(); return; }
            try {
                const res  = await fetch(`${url}?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                // For seller input, show only seller suggestions
                const filtered = filterType ? data.filter(d => d.type === filterType) : data;
                render(filtered, q);
            } catch (_) { hide(); }
        }, 250);

        input.addEventListener("input", function () { fetch_(this.value.trim()); });

        input.addEventListener("keydown", function (e) {
            const items  = qsa(".suggestion-item", box);
            const active = qs(".suggestion-item.suggestion-active", box);
            let idx = items.indexOf(active);
            if (e.key === "ArrowDown") {
                e.preventDefault();
                idx = (idx + 1) % items.length;
                setActive(items, idx);
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                idx = (idx - 1 + items.length) % items.length;
                setActive(items, idx);
            } else if (e.key === "Enter" && active) {
                e.preventDefault();
                apply(active);
            } else if (e.key === "Escape") {
                hide();
            }
        });

        document.addEventListener("click", function (e) {
            if (!input.contains(e.target) && !box.contains(e.target)) hide();
        });

        function render(items, q) {
            if (!items.length) { hide(); return; }
            const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            box.innerHTML = items.map(function (item) {
                const highlighted = item.label.replace(
                    new RegExp(`(${escaped})`, "gi"),
                    "<mark>$1</mark>"
                );
                return `<div class="suggestion-item" data-label="${item.label}" data-type="${item.type}">
                    <i class="bi ${icons[item.type] || "bi-search"} suggestion-icon text-primary"></i>
                    <span class="suggestion-text">${highlighted}</span>
                    <span class="suggestion-sub">${item.sub}</span>
                </div>`;
            }).join("");

            qsa(".suggestion-item", box).forEach(function (el) {
                el.addEventListener("mousedown", function (e) { e.preventDefault(); apply(el); });
            });
            box.classList.remove("d-none");
        }

        function apply(el) {
            const type  = el.dataset.type;
            const label = el.dataset.label;
            hide();
            if (type === "seller") {
                const si = qs("#sellerInput");
                if (si) { si.value = label; qs("#searchInput").value = ""; }
            } else if (type === "category") {
                setCategoryActive(label);
                input.value = "";
            } else {
                input.value = label;
            }
            qs("#filterForm")?.submit();
        }

        function setActive(items, idx) {
            items.forEach(el => el.classList.remove("suggestion-active"));
            if (items[idx]) {
                items[idx].classList.add("suggestion-active");
                input.value = items[idx].dataset.label;
            }
        }

        function hide() {
            box.classList.add("d-none");
            box.innerHTML = "";
        }
    }

    // Init both inputs
    initAutocomplete(qs("#searchInput"),  qs("#suggestionsBox"),        null);
    initAutocomplete(qs("#sellerInput"),  qs("#sellerSuggestionsBox"),  "seller");

    // ── Category selector ────────────────────────────────────────
    function setCategoryActive(cat) {
        const field = qs("#categoryField");
        if (field) field.value = cat;
        qsa(".cat-filter-link").forEach(function (btn) {
            btn.classList.toggle("active", btn.dataset.cat === cat);
        });
    }

    qsa(".cat-filter-link").forEach(function (btn) {
        btn.addEventListener("click", function () {
            setCategoryActive(this.dataset.cat);
            qs("#filterForm")?.submit();
        });
    });

    // ── Women-Owned toggle auto-submit ────────────────────────────
    const verifiedCheck = qs("#verifiedCheck");
    const verifiedLabel = qs(".verified-toggle-label");
    if (verifiedCheck) {
        verifiedCheck.addEventListener("change", function () {
            verifiedLabel?.classList.toggle("verified-toggle-label--on", this.checked);
            qs("#filterForm")?.submit();
        });
    }

    // ── Dual price range slider ───────────────────────────────────
    const sliderMin = qs("#priceMin");
    const sliderMax = qs("#priceMax");
    const inputMin  = qs("#priceMinInput");
    const inputMax  = qs("#priceMaxInput");
    const priceFill = qs("#priceFill");

    if (sliderMin && sliderMax) {
        const FLOOR = parseInt(sliderMin.min);
        const CEIL  = parseInt(sliderMax.max);

        function pct(v) { return ((v - FLOOR) / (CEIL - FLOOR)) * 100; }

        function updateFill() {
            if (!priceFill) return;
            const lo = parseInt(sliderMin.value);
            const hi = parseInt(sliderMax.value);
            priceFill.style.left  = pct(lo) + "%";
            priceFill.style.width = (pct(hi) - pct(lo)) + "%";
        }

        function syncFromSliders() {
            let lo = parseInt(sliderMin.value);
            let hi = parseInt(sliderMax.value);
            if (lo > hi) { [lo, hi] = [hi, lo]; sliderMin.value = lo; sliderMax.value = hi; }
            inputMin.value = lo <= FLOOR ? "" : lo;
            inputMax.value = hi >= CEIL  ? "" : hi;
            updateFill();
        }

        function syncFromInputs() {
            let lo = inputMin.value !== "" ? parseInt(inputMin.value) : FLOOR;
            let hi = inputMax.value !== "" ? parseInt(inputMax.value) : CEIL;
            lo = Math.max(FLOOR, Math.min(lo, CEIL));
            hi = Math.max(FLOOR, Math.min(hi, CEIL));
            if (lo > hi) lo = hi;
            sliderMin.value = lo;
            sliderMax.value = hi;
            updateFill();
        }

        sliderMin.addEventListener("input", syncFromSliders);
        sliderMax.addEventListener("input", syncFromSliders);
        inputMin.addEventListener("input",  syncFromInputs);
        inputMax.addEventListener("input",  syncFromInputs);
        updateFill();
    }

    // ── Star rating filter ────────────────────────────────────────
    const ratingField = qs("#ratingField");
    qsa(".rating-filter-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            qsa(".rating-filter-btn").forEach(b => b.classList.remove("active"));
            this.classList.add("active");
            if (ratingField) ratingField.value = this.dataset.rating;
            qs("#filterForm")?.submit();
        });
    });

})();
