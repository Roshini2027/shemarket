/* SheMarket — cart.js
   Handles: quantity stepper, remove item, live summary update, cart badge */

(function () {
    "use strict";

    const FREE_SHIPPING_THRESHOLD = 50;

    // ── Toast ─────────────────────────────────────────────────────
    function showToast(msg, ok = true) {
        const el = document.getElementById("cartToast");
        if (!el) return;
        el.classList.remove("bg-success", "bg-danger");
        el.classList.add(ok ? "bg-success" : "bg-danger");
        document.getElementById("cartToastMsg").textContent = msg;
        bootstrap.Toast.getOrCreateInstance(el, { delay: 2800 }).show();
    }

    // ── Update navbar badge ───────────────────────────────────────
    function updateBadge(count) {
        document.querySelectorAll(".cart-count-badge").forEach(function (el) {
            el.textContent = count;
            el.style.display = count > 0 ? "" : "none";
        });
    }

    // ── Format currency ───────────────────────────────────────────
    function fmt(n) { return "₹" + parseFloat(n).toFixed(2); }

    // ── Update summary panel ──────────────────────────────────────
    function updateSummary(data) {
        const sub      = document.getElementById("summarySubtotal");
        const ship     = document.getElementById("summaryShipping");
        const tot      = document.getElementById("summaryTotal");
        const bar      = document.getElementById("shippingProgress");
        const freeWrap = document.querySelector(".free-shipping-bar");

        if (sub) sub.textContent = fmt(data.subtotal);
        if (tot) tot.textContent = fmt(data.total);

        if (ship) {
            if (data.shipping === 0) {
                ship.innerHTML = '<span class="text-success">Free</span>';
            } else {
                ship.textContent = fmt(data.shipping);
            }
        }

        if (freeWrap) {
            if (data.subtotal >= FREE_SHIPPING_THRESHOLD) {
                freeWrap.style.display = "none";
            } else {
                freeWrap.style.display = "";
                const pct = Math.min((data.subtotal / FREE_SHIPPING_THRESHOLD) * 100, 100);
                if (bar) bar.style.width = pct + "%";
                const txt = freeWrap.querySelector("strong");
                if (txt) txt.textContent = fmt(FREE_SHIPPING_THRESHOLD - data.subtotal);
            }
        }

        if (data.cart_count !== undefined) updateBadge(data.cart_count);
    }

    // ── Remove item row ───────────────────────────────────────────
    function removeRow(itemId, data) {
        const row = document.getElementById("cart-item-" + itemId);
        if (row) {
            row.style.transition = "opacity 0.25s, max-height 0.3s";
            row.style.opacity = "0";
            row.style.overflow = "hidden";
            row.style.maxHeight = row.offsetHeight + "px";
            setTimeout(function () {
                row.style.maxHeight = "0";
                row.style.padding = "0";
                setTimeout(function () {
                    row.remove();
                    if (!document.querySelector(".cart-item")) showEmptyState();
                }, 300);
            }, 250);
        }
        updateSummary(data);
    }

    function showEmptyState() {
        const list = document.getElementById("cartItemsList");
        if (list) {
            list.closest(".card").closest(".col-lg-8").innerHTML =
                `<div class="text-center py-5">
                    <div class="empty-cart-icon mb-3"><i class="bi bi-cart-x"></i></div>
                    <h6 class="fw-semibold">Your cart is empty</h6>
                    <a href="/catalog" class="btn btn-primary btn-sm rounded-pill mt-2 px-4">
                        <i class="bi bi-bag me-1"></i>Shop Now
                    </a>
                </div>`;
        }
        const summary = document.getElementById("orderSummary");
        if (summary) summary.style.display = "none";
    }

    // ── AJAX helper ───────────────────────────────────────────────
    async function postJSON(url, body) {
        const res = await fetch(url, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(body),
        });
        return res.json();
    }

    // ── Quantity change ───────────────────────────────────────────
    async function changeQuantity(itemId, newQty) {
        try {
            const data = await postJSON(`/cart/update/${itemId}`, { quantity: newQty });
            if (!data.ok) { showToast(data.msg || "Error updating cart.", false); return; }

            if (data.removed) {
                removeRow(itemId, data);
                showToast("Item removed from cart.");
                return;
            }

            const input = document.querySelector(`.qty-input[data-item-id="${itemId}"]`);
            if (input) input.value = data.quantity;

            const lineEl = document.getElementById("line-total-" + itemId);
            if (lineEl) lineEl.textContent = fmt(data.line_total);

            updateSummary(data);
        } catch (_) {
            showToast("Network error. Please try again.", false);
        }
    }

    // ── Stepper buttons ───────────────────────────────────────────
    document.addEventListener("click", function (e) {
        const btn = e.target.closest(".qty-btn");
        if (!btn) return;

        const itemId = btn.dataset.itemId;
        const input  = document.querySelector(`.qty-input[data-item-id="${itemId}"]`);
        if (!input) return;

        let qty = parseInt(input.value);
        if (btn.dataset.action === "inc") {
            const max = parseInt(btn.dataset.max || input.max || 99);
            if (qty < max) qty++;
        } else {
            qty--;
        }
        input.value = qty;
        changeQuantity(itemId, qty);
    });

    // ── Direct input change ───────────────────────────────────────
    document.addEventListener("change", function (e) {
        if (!e.target.classList.contains("qty-input")) return;
        const itemId = e.target.dataset.itemId;
        const qty    = parseInt(e.target.value) || 0;
        changeQuantity(itemId, qty);
    });

    // ── Remove button ─────────────────────────────────────────────
    document.addEventListener("click", async function (e) {
        const btn = e.target.closest(".remove-btn");
        if (!btn) return;
        const itemId = btn.dataset.itemId;
        try {
            const data = await postJSON(`/cart/remove/${itemId}`, {});
            if (!data.ok) { showToast(data.msg || "Error.", false); return; }
            removeRow(itemId, data);
            showToast("Item removed from cart.");
        } catch (_) {
            showToast("Network error. Please try again.", false);
        }
    });

})();


// ── Add-to-Cart (used on product detail & catalog cards) ──────────────────────
window.addToCart = async function (productId, quantity, btnEl) {
    if (btnEl) {
        btnEl.disabled = true;
        btnEl.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Adding…';
    }
    try {
        const res  = await fetch("/cart/add", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ product_id: productId, quantity: quantity || 1 }),
        });
        const data = await res.json();

        if (btnEl) {
            if (data.ok) {
                btnEl.innerHTML = '<i class="bi bi-check-lg me-1"></i>Added!';
                btnEl.classList.replace("btn-primary", "btn-success");
                setTimeout(function () {
                    btnEl.disabled = false;
                    btnEl.innerHTML = '<i class="bi bi-cart-plus me-2"></i>Add to Cart';
                    btnEl.classList.replace("btn-success", "btn-primary");
                }, 1800);
            } else {
                btnEl.disabled = false;
                btnEl.innerHTML = '<i class="bi bi-cart-plus me-2"></i>Add to Cart';
            }
        }

        // Update navbar badge
        if (data.cart_count !== undefined) {
            document.querySelectorAll(".cart-count-badge").forEach(function (el) {
                el.textContent = data.cart_count;
                el.style.display = data.cart_count > 0 ? "" : "none";
            });
        }

        // Toast
        const toastEl = document.getElementById("cartToast");
        if (toastEl) {
            toastEl.classList.remove("bg-success", "bg-danger");
            toastEl.classList.add(data.ok ? "bg-success" : "bg-danger");
            document.getElementById("cartToastMsg").textContent = data.msg;
            bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 2800 }).show();
        }
    } catch (_) {
        if (btnEl) {
            btnEl.disabled = false;
            btnEl.innerHTML = '<i class="bi bi-cart-plus me-2"></i>Add to Cart';
        }
    }
};
