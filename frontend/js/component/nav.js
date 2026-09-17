document.addEventListener("DOMContentLoaded", () => {

    // =========================================================
    // CURRENT URL
    // =========================================================

    const currentPath = window.location.pathname.toLowerCase();


    // =========================================================
    // NAVIGATION STYLES
    // =========================================================

    const activeNavClasses =
        "relative text-xs font-black text-slate-950 " +
        "bg-gradient-to-r from-teal-400 via-cyan-400 to-emerald-400 " +
        "px-6 py-2.5 rounded-full " +
        "shadow-[0_4px_15px_rgba(45,212,191,0.4)] " +
        "transition-all duration-300 " +
        "whitespace-nowrap tracking-wider uppercase";

    const inactiveNavClasses =
        "text-xs font-bold text-slate-300 " +
        "hover:text-teal-400 " +
        "px-5 py-2.5 rounded-full " +
        "hover:bg-white/5 " +
        "transition-all duration-300 " +
        "whitespace-nowrap tracking-wider uppercase";


    // =========================================================
    // DETERMINE CURRENT PAGE
    // =========================================================

    function getCurrentPage() {

        // HOME
        if (
            currentPath.endsWith("/") ||
            currentPath.endsWith("/index.html") ||
            currentPath.endsWith("index.html")
        ) {
            return "home";
        }

        // PUBLIC PAGES
        if (currentPath.includes("about.html")) {
            return "about";
        }

        if (currentPath.includes("how-it-works.html")) {
            return "how-it-works";
        }

        if (currentPath.includes("contact.html")) {
            return "contact";
        }

        // CUSTOMER PAGES
        if (currentPath.includes("menu.html")) {
            return "menu";
        }

        if (currentPath.includes("preorder.html")) {
            return "preorder";
        }

        if (currentPath.includes("orders.html")) {
            return "orders";
        }

        if (currentPath.includes("expenses.html")) {
            return "expenses";
        }

        if (currentPath.includes("income.html")) {
            return "income";
        }

        if (currentPath.includes("budgets.html") || currentPath.includes("goals.html")) {
            return "budgets";
        }

        if (currentPath.includes("analytics.html")) {
            return "analytics";
        }

        if (currentPath.includes("assistant.html")) {
            return "assistant";
        }

        if (currentPath.includes("profile.html")) {
            return "profile";
        }

        // AUTH PAGES
        if (currentPath.includes("login.html")) {
            return "login";
        }

        if (currentPath.includes("signup.html")) {
            return "signup";
        }

        return "";
    }


    const currentPage = getCurrentPage();


    // =========================================================
    // DESKTOP NAVIGATION
    // =========================================================

    function highlightDesktopNavigation() {

        const desktopLinks =
            document.querySelectorAll("#desktop-nav .nav-link");

        desktopLinks.forEach((link) => {

            const page = link.dataset.page;

            // Reset
            link.className = inactiveNavClasses;

            // Active
            if (page === currentPage) {
                link.className = activeNavClasses;
            }

        });
    }


    // =========================================================
    // MOBILE BOTTOM NAVIGATION
    // =========================================================

    function highlightMobileNavigation() {

        const mobileLinks =
            document.querySelectorAll(".mobile-nav-link");

        if (!mobileLinks.length) {
            return;
        }

        mobileLinks.forEach((link) => {

            const page = link.dataset.page;

            const activeIndicator =
                link.querySelector(".nav-active-indicator");

            const icon =
                link.querySelector(".mobile-nav-icon");

            const label =
                link.querySelector(".mobile-nav-label");


            // -------------------------------------------------
            // RESET
            // -------------------------------------------------

            if (activeIndicator) {
                activeIndicator.classList.add("hidden");
            }

            if (icon) {
                icon.classList.remove("text-teal-400");
                icon.classList.add("text-slate-400");
            }

            if (label) {
                label.classList.remove(
                    "text-teal-400",
                    "font-black"
                );

                label.classList.add(
                    "text-slate-400",
                    "font-bold"
                );
            }


            // -------------------------------------------------
            // PROFILE / LOGIN
            // -------------------------------------------------

            let isActive = page === currentPage;

            if (
                page === "profile" &&
                (
                    currentPage === "profile" ||
                    currentPage === "login"
                )
            ) {
                isActive = true;
            }


            // -------------------------------------------------
            // APPLY ACTIVE
            // -------------------------------------------------

            if (isActive) {

                if (activeIndicator) {
                    activeIndicator.classList.remove("hidden");
                }

                if (icon) {
                    icon.classList.remove("text-slate-400");
                    icon.classList.add("text-teal-400");
                }

                if (label) {
                    label.classList.remove(
                        "text-slate-400",
                        "font-bold"
                    );

                    label.classList.add(
                        "text-teal-400",
                        "font-black"
                    );
                }
            }

        });
    }


    // =========================================================
    // INITIALIZE NAVIGATION
    // =========================================================

    function initializeNavigation() {
        highlightDesktopNavigation();
        highlightMobileNavigation();
    }


    // =========================================================
    // START
    // =========================================================

    initializeNavigation();

});