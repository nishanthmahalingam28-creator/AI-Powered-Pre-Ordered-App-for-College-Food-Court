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

            // Reset link
            link.className = inactiveNavClasses;

            // Apply active style
            if (page === currentPage) {
                link.className = activeNavClasses;
            }

        });
    }


    // =========================================================
    // MOBILE / TABLET NAVIGATION
    // =========================================================

    function highlightMobileNavigation() {

        const mobileDock =
            document.querySelector(".fixed.bottom-4 nav");

        if (!mobileDock) {
            return;
        }

        const mobileLinks =
            mobileDock.querySelectorAll("a");


        mobileLinks.forEach((tab) => {

            const href =
                (tab.getAttribute("href") || "").toLowerCase();

            const activePill =
                tab.querySelector("span.absolute.-top-2");

            const icon =
                tab.querySelector("svg");

            const label =
                tab.querySelector("span:not(.absolute)");


            // =================================================
            // DETERMINE ACTIVE TAB
            // =================================================

            let isActive = false;


            // HOME
            if (
                currentPage === "home" &&
                href.includes("index.html")
            ) {
                isActive = true;
            }


            // MENU
            if (
                currentPage === "menu" &&
                href.includes("menu.html")
            ) {
                isActive = true;
            }


            // PRE-ORDER
            if (
                currentPage === "preorder" &&
                href.includes("preorder.html")
            ) {
                isActive = true;
            }


            // ORDERS
            if (
                currentPage === "orders" &&
                href.includes("orders.html")
            ) {
                isActive = true;
            }


            // PROFILE / LOGIN
            if (
                (
                    currentPage === "profile" ||
                    currentPage === "login"
                ) &&
                href.includes("login.html")
            ) {
                isActive = true;
            }


            // =================================================
            // RESET TAB
            // =================================================

            if (activePill) {
                activePill.classList.add("hidden");
            }

            if (icon) {

                icon.classList.remove(
                    "text-[#14b8a6]"
                );

                icon.classList.add(
                    "text-slate-400"
                );
            }

            if (label) {

                label.classList.remove(
                    "text-[#14b8a6]",
                    "font-black"
                );

                label.classList.add(
                    "text-slate-400",
                    "font-bold"
                );
            }


            // =================================================
            // APPLY ACTIVE TAB
            // =================================================

            if (isActive) {

                if (activePill) {
                    activePill.classList.remove("hidden");
                }

                if (icon) {

                    icon.classList.remove(
                        "text-slate-400"
                    );

                    icon.classList.add(
                        "text-[#14b8a6]"
                    );
                }

                if (label) {

                    label.classList.remove(
                        "text-slate-400",
                        "font-bold"
                    );

                    label.classList.add(
                        "text-[#14b8a6]",
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
    // LOAD NAVBAR COMPONENT
    // =========================================================

    const navbarContainer =
        document.getElementById("navbar");


    if (navbarContainer) {

        const isNested =
            currentPath.includes("/pages/");

        const componentPath =
            isNested
                ? "../../components/"
                : "components/";


        fetch(componentPath + "navbar.html")

            .then((response) => {

                if (!response.ok) {

                    throw new Error(
                        "Navbar component failed to load."
                    );

                }

                return response.text();

            })

            .then((html) => {

                navbarContainer.innerHTML = html;

                initializeNavigation();

            })

            .catch((error) => {

                console.error(
                    "Navbar loading error:",
                    error
                );

            });

    } else {

        // Navbar already exists in HTML
        initializeNavigation();

    }


    // =========================================================
    // LOAD FOOTER COMPONENT
    // =========================================================

    const footerContainer =
        document.getElementById("footer");


    if (footerContainer) {

        const isNested =
            currentPath.includes("/pages/");

        const componentPath =
            isNested
                ? "../../components/"
                : "components/";


        fetch(componentPath + "footer.html")

            .then((response) => {

                if (!response.ok) {

                    throw new Error(
                        "Footer component failed to load."
                    );

                }

                return response.text();

            })

            .then((html) => {

                footerContainer.innerHTML = html;

            })

            .catch((error) => {

                console.error(
                    "Footer loading error:",
                    error
                );

            });

    }

});