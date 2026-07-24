// ================================
// Customer Dashboard JavaScript
// AI Powered Pre-Order Food Court
// ================================

// Welcome Message
document.addEventListener("DOMContentLoaded", () => {

    const username = "Nishanth"; // Later load from database

    const heading = document.querySelector(".welcome h1");

    if (heading) {
        heading.innerHTML = `Welcome, ${username} 👋`;
    }

});

// -------------------------------
// Search Function
// -------------------------------

const searchInput = document.querySelector(".search-box input");

if (searchInput) {

    searchInput.addEventListener("keyup", function () {

        let value = this.value.toLowerCase();

        let shops = document.querySelectorAll(".shop-card");

        shops.forEach((shop) => {

            let text = shop.innerText.toLowerCase();

            if (text.includes(value)) {
                shop.style.display = "block";
            } else {
                shop.style.display = "none";
            }

        });

    });

}

// -------------------------------
// View Menu Buttons
// -------------------------------

const menuButtons = document.querySelectorAll(".shop-card button");

menuButtons.forEach((button) => {

    button.addEventListener("click", () => {

        alert("Opening Menu...");

        // Later
        // window.location.href = "menu.html";

    });

});

// -------------------------------
// AI Recommendation Button
// -------------------------------

const aiButton = document.querySelector(".recommend button");

if (aiButton) {

    aiButton.addEventListener("click", () => {

        alert("Added AI Recommended Food to Cart");

    });

}

// -------------------------------
// Notification Icon
// -------------------------------

const bell = document.querySelector(".fa-bell");

if (bell) {

    bell.addEventListener("click", () => {

        alert("No New Notifications");

    });

}

// -------------------------------
// Cart Icon
// -------------------------------

const cart = document.querySelector(".fa-cart-shopping");

if (cart) {

    cart.addEventListener("click", () => {

        alert("Opening Cart");

        // window.location.href = "cart.html";

    });

}

// -------------------------------
// Profile Image
// -------------------------------

const profile = document.querySelector(".profile");

if (profile) {

    profile.addEventListener("click", () => {

        alert("Opening Profile");

        // window.location.href = "profile.html";

    });

}

// -------------------------------
// Quick Actions
// -------------------------------

const actions = document.querySelectorAll(".action");

actions.forEach((action) => {

    action.addEventListener("click", () => {

        const title = action.querySelector("h3").innerText;

        switch (title) {

            case "My Orders":
                alert("Opening My Orders");
                // window.location.href = "orders.html";
                break;

            case "Order History":
                alert("Opening Order History");
                break;

            case "Favourite":
                alert("Opening Favourite Items");
                break;

            case "Profile":
                alert("Opening Profile");
                break;

        }

    });

});

// -------------------------------
// Shop Card Hover Animation
// -------------------------------

const cards = document.querySelectorAll(".shop-card");

cards.forEach((card) => {

    card.addEventListener("mouseenter", () => {

        card.style.transform = "translateY(-8px)";
        card.style.transition = "0.3s";

    });

    card.addEventListener("mouseleave", () => {

        card.style.transform = "translateY(0px)";

    });

});

// -------------------------------
// Fake Notification Counter
// -------------------------------

let notification = document.querySelector(".fa-bell + span");

if (notification) {

    setTimeout(() => {

        notification.innerText = "3";

    }, 5000);

}

// -------------------------------
// Greeting Based on Time
// -------------------------------

const hour = new Date().getHours();

let greeting = "";

if (hour < 12) {

    greeting = "Good Morning ☀️";

} else if (hour < 17) {

    greeting = "Good Afternoon 🌤️";

} else {

    greeting = "Good Evening 🌙";

}

console.log(greeting);

// -------------------------------
// Current Date
// -------------------------------

const today = new Date();

console.log(today.toDateString());

// -------------------------------
// Future API Integration
// -------------------------------

// Fetch Customer Details
// Fetch Shop Details
// Fetch Menu
// Fetch AI Recommendation
// Fetch Orders
// Fetch Notifications
// Fetch Cart

console.log("Customer Dashboard Loaded Successfully");