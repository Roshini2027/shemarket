/* SheMarket — reviews.js
   Handles: star picker, submit, edit, delete, live avg update, show-more */

(function () {
    "use strict";

    const LABELS = { 1: "Poor", 2: "Fair", 3: "Good", 4: "Very Good", 5: "Excellent" };

    // ── Helpers ───────────────────────────────────────────────────
    function qs(sel, ctx)  { return (ctx || document).querySelector(sel); }
    function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

    async function jsonRequest(url, method, body) {
        const res = await fetch(url, {
            method,
            headers: { "Content-Type": "application/json" },
            body: body ? JSON.stringify(body) : undefined,
        });
        return res.json();
    }

    function showAlert(msg, type = "success") {
        const wrap = qs("#reviewAlertWrap");
        if (!wrap) return;
        wrap.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show rounded-3 small py-2" role="alert">
                ${msg}
                <button type="button" class="btn-close btn-close-sm" data-bs-dismiss="alert"></button>
            </div>`;
        wrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function setBtn(btn, loading) {
        if (!btn) return;
        btn._origHTML = btn._origHTML || btn.innerHTML;
        btn.disabled  = loading;
        btn.innerHTML = loading
            ? '<span class="spinner-border spinner-border-sm me-1"></span>Saving…'
            : btn._origHTML;
    }

    // ── Star picker factory ───────────────────────────────────────
    function initStarPicker(pickerId, inputId, labelId) {
        const picker = qs("#" + pickerId);
        const input  = qs("#" + inputId);
        const label  = labelId ? qs("#" + labelId) : null;
        if (!picker || !input) return;

        const stars = qsa(".review-pick-star", picker);

        function paint(val) {
            stars.forEach(function (s) {
                const v = parseInt(s.dataset.value);
                s.classList.toggle("active",   v <= val);
                s.classList.toggle("bi-star-fill", true);
                s.classList.remove("bi-star");
                if (v <= val) s.classList.add("active");
                else          s.classList.remove("active");
            });
            if (label) label.textContent = LABELS[val] || "\u00a0";
        }

        stars.forEach(function (s) {
            s.addEventListener("mouseenter", function () { paint(parseInt(this.dataset.value)); });
            s.addEventListener("mouseleave", function () { paint(parseInt(input.value) || 0); });
            s.addEventListener("click",      function () {
                input.value = this.dataset.value;
                paint(parseInt(this.dataset.value));
            });
        });

        // Init from existing value
        paint(parseInt(input.value) || 0);
    }

    initStarPicker("newStarPicker",  "newRatingInput",  "newRatingLabel");
    initStarPicker("editStarPicker", "editRatingInput", "editRatingLabel");

    // ── Char counter ──────────────────────────────────────────────
    function initCharCounter(textareaId, counterId) {
        const ta  = qs("#" + textareaId);
        const cnt = qs("#" + counterId);
        if (!ta || !cnt) return;
        function update() { cnt.textContent = ta.value.length + " / 2000"; }
        ta.addEventListener("input", update);
        update();
    }

    initCharCounter("newCommentInput",  "charCount");
    initCharCounter("editCommentInput", "editCharCount");

    // ── Build review card HTML ────────────────────────────────────
    function buildStars(rating) {
        let html = "";
        for (let i = 1; i <= 5; i++) {
            html += `<i class="bi bi-star-fill review-star ${i <= rating ? "filled" : ""}"></i>`;
        }
        return html;
    }

    function buildCard(r) {
        return `
        <div class="review-card card border-0 shadow-sm rounded-4 mb-3 review-card--new" id="review-${r.id}">
            <div class="card-body p-4">
                <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap mb-2">
                    <div class="d-flex align-items-center gap-2">
                        <div class="review-avatar">${r.author[0].toUpperCase()}</div>
                        <div>
                            <div class="fw-semibold small">${r.author}</div>
                            <div class="text-secondary" style="font-size:0.72rem;">${r.created_at}${r.was_edited ? ' <span class="ms-1 fst-italic">(edited)</span>' : ""}</div>
                        </div>
                    </div>
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        <span class="review-star-display">${buildStars(r.rating)}</span>
                        <span class="badge bg-warning-soft text-warning rounded-pill small px-2 py-1">${r.rating_label}</span>
                    </div>
                </div>
                ${r.title ? `<div class="fw-semibold mb-1 small review-title">${r.title}</div>` : ""}
                ${r.comment
                    ? `<p class="text-secondary small mb-0 lh-lg review-body">${r.comment}</p>`
                    : `<p class="text-secondary small mb-0 fst-italic">No written review.</p>`}
            </div>
        </div>`;
    }

    // ── Update avg rating in header and summary card ──────────────
    function updateAvgDisplay(avg, count) {
        const avgEl    = qs("#avgRatingDisplay");
        const headerEl = qs("#headerAvg");
        const countEl  = qs("#reviewCount");
        const hCount   = qs("#headerReviewCount");

        if (avgEl)    avgEl.textContent    = avg;
        if (headerEl) headerEl.textContent = avg;
        if (countEl)  countEl.textContent  = count + " review" + (count !== 1 ? "s" : "");
        if (hCount)   hCount.textContent   = "(" + count + " review" + (count !== 1 ? "s" : "") + ")";
    }

    // ── Submit new review ─────────────────────────────────────────
    const submitBtn = qs("#submitReviewBtn");
    if (submitBtn) {
        submitBtn.addEventListener("click", async function () {
            const rating  = parseInt(qs("#newRatingInput")?.value || "0");
            const title   = qs("#newTitleInput")?.value.trim()   || "";
            const comment = qs("#newCommentInput")?.value.trim() || "";

            if (!rating) { showAlert("Please select a star rating.", "warning"); return; }

            setBtn(this, true);
            try {
                const data = await jsonRequest(this.dataset.url, "POST", { rating, title, comment });
                if (!data.ok) { showAlert(data.msg, "danger"); return; }

                // Prepend new card
                const list = qs("#reviewList");
                const noMsg = qs("#noReviewsMsg");
                if (noMsg)  noMsg.remove();
                if (list)   list.insertAdjacentHTML("afterbegin", buildCard(data.review));

                // Clear form
                qs("#newRatingInput").value  = "0";
                qs("#newTitleInput").value   = "";
                qs("#newCommentInput").value = "";
                initStarPicker("newStarPicker", "newRatingInput", "newRatingLabel");
                qs("#charCount").textContent = "0 / 2000";

                updateAvgDisplay(data.avg_rating, data.count);
                showAlert(data.msg, "success");
            } catch (_) {
                showAlert("Network error. Please try again.", "danger");
            } finally {
                setBtn(submitBtn, false);
            }
        });
    }

    // ── Edit existing review ──────────────────────────────────────
    const editBtn = qs("#editReviewBtn");
    if (editBtn) {
        editBtn.addEventListener("click", async function () {
            const rating  = parseInt(qs("#editRatingInput")?.value || "0");
            const title   = qs("#editTitleInput")?.value.trim()   || "";
            const comment = qs("#editCommentInput")?.value.trim() || "";

            if (!rating) { showAlert("Please select a star rating.", "warning"); return; }

            setBtn(this, true);
            try {
                const data = await jsonRequest(this.dataset.url, "PUT", { rating, title, comment });
                if (!data.ok) { showAlert(data.msg, "danger"); return; }

                // Update existing card in the list
                const card = qs("#review-" + data.review.id);
                if (card) {
                    const stars = qs(".review-star-display", card);
                    const label = qs(".badge",               card);
                    const titleEl   = qs(".review-title",   card);
                    const commentEl = qs(".review-body",     card);
                    const dateEl    = card.querySelector(".text-secondary[style]");

                    if (stars) stars.innerHTML = buildStars(data.review.rating);
                    if (label) label.textContent = data.review.rating_label;

                    if (titleEl) {
                        titleEl.textContent = data.review.title;
                        titleEl.style.display = data.review.title ? "" : "none";
                    }
                    if (commentEl) commentEl.textContent = data.review.comment || "";
                    if (dateEl && data.review.was_edited) {
                        if (!dateEl.querySelector(".fst-italic")) {
                            dateEl.insertAdjacentHTML("beforeend", ' <span class="ms-1 fst-italic">(edited)</span>');
                        }
                    }
                }

                updateAvgDisplay(data.avg_rating, qs("#reviewCount")?.textContent.match(/\d+/)?.[0] || "—");
                showAlert(data.msg, "success");
            } catch (_) {
                showAlert("Network error. Please try again.", "danger");
            } finally {
                setBtn(editBtn, false);
            }
        });
    }

    // ── Delete review ─────────────────────────────────────────────
    const deleteBtn = qs("#deleteReviewBtn");
    if (deleteBtn) {
        deleteBtn.addEventListener("click", async function () {
            if (!confirm("Delete your review? This cannot be undone.")) return;
            setBtn(this, true);
            try {
                const data = await jsonRequest(this.dataset.url, "DELETE");
                if (!data.ok) { showAlert(data.msg, "danger"); return; }

                // Remove card and hide edit form
                const card = qs("#review-" + this.dataset.reviewId);
                if (card)  card.remove();

                const myCard = qs("#myReviewCard");
                if (myCard) myCard.remove();

                updateAvgDisplay(data.avg_rating, data.count);

                if (data.count === 0) {
                    const list = qs("#reviewList");
                    if (list) list.innerHTML = `
                        <div class="text-center py-5" id="noReviewsMsg">
                            <i class="bi bi-chat-square-text fs-1 text-secondary opacity-40 d-block mb-3"></i>
                            <p class="text-secondary">No reviews yet. Be the first to review this product!</p>
                        </div>`;
                }
                showAlert(data.msg, "info");
            } catch (_) {
                showAlert("Network error. Please try again.", "danger");
            } finally {
                setBtn(deleteBtn, false);
            }
        });
    }

    // ── Show more / less ──────────────────────────────────────────
    const showMoreBtn = qs("#showMoreBtn");
    if (showMoreBtn) {
        const allCards = qsa(".review-card");
        const STEP = 5;
        let shown = STEP;

        // Hide cards beyond initial count
        allCards.forEach(function (c, i) { if (i >= shown) c.style.display = "none"; });

        showMoreBtn.addEventListener("click", function () {
            const remaining = allCards.filter(c => c.style.display === "none");
            remaining.slice(0, STEP).forEach(c => { c.style.display = ""; });
            shown += STEP;
            if (shown >= allCards.length) this.style.display = "none";
        });
    }

})();
