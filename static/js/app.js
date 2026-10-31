document.addEventListener("DOMContentLoaded", function () {
    const body = document.body;
    const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
    const sidebarClose = document.querySelector("[data-sidebar-close]");

    if (sidebarToggle) {
        sidebarToggle.addEventListener("click", function () {
            body.classList.toggle("sidebar-open");
        });
    }

    if (sidebarClose) {
        sidebarClose.addEventListener("click", function () {
            body.classList.remove("sidebar-open");
        });
    }

    document.querySelectorAll(".sidebar .nav-link").forEach(function (link) {
        link.addEventListener("click", function () {
            body.classList.remove("sidebar-open");
        });
    });

    document.querySelectorAll("[data-dropdown]").forEach(function (dropdown) {
        const toggle = dropdown.querySelector("[data-dropdown-toggle]");
        if (!toggle) return;
        toggle.addEventListener("click", function (event) {
            event.stopPropagation();
            document.querySelectorAll("[data-dropdown].is-open").forEach(function (open) {
                if (open !== dropdown) open.classList.remove("is-open");
            });
            dropdown.classList.toggle("is-open");
        });
    });

    document.addEventListener("click", function (event) {
        document.querySelectorAll("[data-dropdown].is-open").forEach(function (dropdown) {
            if (!dropdown.contains(event.target)) dropdown.classList.remove("is-open");
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            document.querySelectorAll("[data-dropdown].is-open").forEach(function (dropdown) {
                dropdown.classList.remove("is-open");
            });
            body.classList.remove("sidebar-open");
        }
    });

    document.querySelectorAll("[data-dismiss]").forEach(function (button) {
        button.addEventListener("click", function () {
            const flash = button.closest(".flash");
            if (flash) flash.remove();
        });
    });

    document.querySelectorAll(".table-wrap").forEach(function (wrap) {
        function update() {
            wrap.classList.toggle("is-scrollable", wrap.scrollWidth > wrap.clientWidth + 4);
        }
        update();
        wrap.addEventListener("scroll", update, { passive: true });
        window.addEventListener("resize", update);
    });

    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        const input = document.getElementById(button.getAttribute("data-password-toggle"));
        if (!input) return;
        button.addEventListener("click", function () {
            const show = input.type === "password";
            input.type = show ? "text" : "password";
            button.classList.toggle("is-visible", show);
            button.setAttribute("aria-pressed", show ? "true" : "false");
            button.setAttribute(
                "aria-label",
                show ? "Hide password" : "Show password"
            );
            input.focus();
        });
    });

    document.querySelectorAll(".flash--success, .flash--info").forEach(function (flash) {
        window.setTimeout(function () {
            flash.style.opacity = "0";
            flash.style.transform = "translateY(-4px)";
            flash.style.transition = "opacity .25s ease, transform .25s ease";
            window.setTimeout(function () { flash.remove(); }, 260);
        }, 6000);
    });

    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!window.confirm(form.getAttribute("data-confirm"))) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll("[data-gallery-thumb]").forEach(function (thumb) {
        thumb.addEventListener("click", function () {
            const main = document.querySelector("[data-gallery-main]");
            if (!main) return;
            main.src = thumb.getAttribute("data-src");
            document.querySelectorAll("[data-gallery-thumb]").forEach(function (item) {
                item.classList.remove("is-active");
            });
            thumb.classList.add("is-active");
        });
    });

    const formsetRows = document.querySelector("[data-formset-rows]");
    const formsetAdd = document.querySelector("[data-formset-add]");
    const formsetEmpty = document.querySelector("[data-formset-empty]");

    if (formsetRows && formsetAdd && formsetEmpty) {
        formsetAdd.addEventListener("click", function () {
            const totalInput = document.querySelector('input[name$="-TOTAL_FORMS"]');
            if (!totalInput) return;
            const index = parseInt(totalInput.value, 10);
            let html = formsetEmpty.innerHTML.replace(/__prefix__/g, index);
            const wrapper = document.createElement("div");
            wrapper.innerHTML = html.trim();
            const row = wrapper.firstElementChild;
            if (!row) return;
            formsetRows.appendChild(row);
            totalInput.value = index + 1;
            row.querySelectorAll("input, select, textarea").forEach(function (field) {
                field.removeAttribute("required");
            });
        });
    }

    document.querySelectorAll("[data-formset-rows]").forEach(function (rows) {
        rows.addEventListener("click", function (event) {
            const remove = event.target.closest("[data-formset-remove]");
            if (!remove) return;
            const row = remove.closest("[data-formset-row]");
            if (!row) return;
            const deleteBox = row.querySelector('input[name$="-DELETE"]');
            const fileInput = row.querySelector('input[type="file"]');
            if (deleteBox) {
                deleteBox.checked = true;
                row.style.display = "none";
            } else if (fileInput && !fileInput.value) {
                row.remove();
            }
        });
    });
});
