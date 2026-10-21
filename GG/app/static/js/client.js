/* =====================================================================
   static/js/client.js
   Behaviour shared by Add Client and Edit Client pages:
     • Spouse section visibility based on Civil Status
     • Government ID formset add / remove / "Other" toggle
     • Beneficiary formset add / remove / Relationship "Other" toggle
   ===================================================================== */
(function () {
    'use strict';

    // ── Spouse section toggle ────────────────────────────────────────
    var civilStatusEl = document.getElementById("id_client_civil_status");
    var spouseSection = document.getElementById("spouse-section");
    var spouseHint    = document.getElementById("spouse-hint");

    var HINTS = {
        Married:   "(required — living spouse)",
        Widowed:   "(optional — deceased spouse)",
        Separated: "(optional — former spouse)"
    };

    function toggleSpouse() {
        if (!civilStatusEl || !spouseSection) return;
        var status = civilStatusEl.value;
        if (status === "Single" || status === "") {
            spouseSection.style.display = "none";
            spouseSection.querySelectorAll("input").forEach(function (f) { f.value = ""; });
        } else {
            spouseSection.style.display = "";
            if (spouseHint) spouseHint.textContent = HINTS[status] || "";
        }
    }

    if (civilStatusEl) {
        civilStatusEl.addEventListener("change", toggleSpouse);
        toggleSpouse();
    }

    // ── Government ID: per-row "Other" toggle ────────────────────────
    function wireGovIdRow(row) {
        if (!row) return;
        var select  = row.querySelector(".id-type-select");
        var wrapper = row.querySelector(".id-type-other-wrapper");
        var other   = row.querySelector(".id-type-other");
        if (!select || !wrapper || !other) return;

        function toggle() {
            var show = select.value === "Other";
            wrapper.classList.toggle("d-none", !show);
            other.required = show;
            if (!show) other.value = "";
        }
        select.addEventListener("change", toggle);
        toggle();
    }

    document.querySelectorAll(".government-id-row").forEach(wireGovIdRow);

    // ── Beneficiary: per-row Relationship "Other" toggle ─────────────
    function wireBeneficiaryRow(row) {
        if (!row) return;
        var select         = row.querySelector(".beneficiary-relationship-select");
        var wrapper        = row.querySelector(".beneficiary-specify-wrapper");
        var specifyInput   = row.querySelector(".beneficiary-specify-input");
        var nameCol        = row.querySelector(".beneficiary-name-col");
        var relCol         = row.querySelector(".beneficiary-rel-col");
        if (!select || !wrapper) return;

        function toggle() {
            var isOther = select.value === "Other";

            // Show / hide the Specify Relationship column
            wrapper.classList.toggle("d-none", !isOther);

            // Rebalance the grid so the row fills the width either way.
            //  • Other   : Name(4) + Rel(3) + Specify(4)  = 11 + Remove(2) → but 4+3+4+2 = 13 too wide
            //  • Better  : Name(4) + Rel(3) + Specify(3)  = 10 + Remove(2) = 12 ✓
            //  • No other: Name(5) + Rel(5)               = 10 + Remove(2) = 12 ✓
            if (nameCol) {
                nameCol.className = isOther
                    ? "col-md-4 beneficiary-name-col"
                    : "col-md-5 beneficiary-name-col";
            }
            if (relCol) {
                relCol.className = isOther
                    ? "col-md-3 beneficiary-rel-col"
                    : "col-md-5 beneficiary-rel-col";
            }
            if (wrapper) {
                wrapper.className = isOther
                    ? "col-md-3 beneficiary-specify-wrapper"
                    : "col-md-3 d-none beneficiary-specify-wrapper";
            }

            // Clear the custom value when leaving "Other"
            if (!isOther && specifyInput) {
                specifyInput.value = "";
            }
        }

        select.addEventListener("change", toggle);
        toggle();
    }

    document.querySelectorAll(".beneficiary-row").forEach(wireBeneficiaryRow);

    // ── Beneficiary: add row ─────────────────────────────────────────
    var addBeneficiaryBtn = document.getElementById("add-beneficiary");
    if (addBeneficiaryBtn) {
        addBeneficiaryBtn.addEventListener("click", function () {
            var wrapper    = document.getElementById("beneficiaries-wrapper");
            var totalForms = document.getElementById("id_beneficiaries-TOTAL_FORMS");
            var template   = document.getElementById("beneficiary-template");
            if (!wrapper || !totalForms || !template) return;

            var count = parseInt(totalForms.value, 10);
            var html  = template.innerHTML.replace(/__prefix__/g, count);
            wrapper.insertAdjacentHTML("beforeend", html);
            totalForms.value = count + 1;

            // Wire up the newly-added row's Relationship toggle
            wireBeneficiaryRow(wrapper.lastElementChild);
        });
    }

    // ── Government ID: add row ───────────────────────────────────────
    var addGovIdBtn = document.getElementById("add-government-id");
    if (addGovIdBtn) {
        addGovIdBtn.addEventListener("click", function () {
            var wrapper    = document.getElementById("government-ids-wrapper");
            var totalForms = document.getElementById("id_government_ids-TOTAL_FORMS");
            var template   = document.getElementById("government-id-template");
            if (!wrapper || !totalForms || !template) return;

            var count = parseInt(totalForms.value, 10);
            var html  = template.innerHTML.replace(/__prefix__/g, count);
            wrapper.insertAdjacentHTML("beforeend", html);
            totalForms.value = count + 1;

            wireGovIdRow(wrapper.lastElementChild);
        });
    }

    // ── Unified remove handler ───────────────────────────────────────
    document.addEventListener("click", function (e) {
        var target = e.target;
        if (!target) return;

        // Beneficiary row removal
        if (target.classList.contains("remove-btn")) {
            var bRow = target.closest(".beneficiary-row");
            if (bRow) {
                var bDelete = bRow.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (bDelete && bRow.querySelector('input[name$="-id"]')) {
                    bDelete.checked = true;
                    bRow.style.display = "none";
                } else {
                    bRow.remove();
                    var bTotal = document.getElementById("id_beneficiaries-TOTAL_FORMS");
                    if (bTotal) bTotal.value = parseInt(bTotal.value, 10) - 1;
                }
            }
            return;
        }

        // Government ID row removal
        if (target.classList.contains("remove-government-id-btn")) {
            var gRow = target.closest(".government-id-row");
            if (!gRow) return;

            var gDelete = gRow.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (gDelete) {
                gDelete.checked = true;
                gRow.style.display = "none";
            } else {
                gRow.remove();
                var gTotal = document.getElementById("id_government_ids-TOTAL_FORMS");
                if (gTotal) gTotal.value = parseInt(gTotal.value, 10) - 1;
            }
        }
    });
})();