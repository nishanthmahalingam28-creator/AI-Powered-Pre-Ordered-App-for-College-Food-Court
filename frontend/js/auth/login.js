const customerTypeSelect = document.getElementById("customerType");
const emailLabel = document.getElementById("emailLabel");
const emailInput = document.getElementById("email");
const emailError = document.getElementById("emailError");
const passwordError = document.getElementById("passwordError");

customerTypeSelect.addEventListener("change", function () {
    if (this.value === "guest") {
        emailLabel.innerText = "Email ID";
        emailInput.placeholder = "example@gmail.com";
    } else {
        emailLabel.innerText = "Institute Email ID";
        emailInput.placeholder = "example@kpriet.ac.in";
    }
    emailError.innerHTML = "";
});

document.getElementById("loginForm").addEventListener("submit", function (event) {
    event.preventDefault();

    const email = emailInput.value.trim();
    const password = document.getElementById("password").value.trim();
    const customerType = customerTypeSelect.value;

    emailError.innerHTML = "";
    passwordError.innerHTML = "";

    let valid = true;

    if (email === "") {
        emailError.innerHTML = "Email is required";
        valid = false;
    } else if (customerType === "student" || customerType === "faculty") {
        const kprietPattern = /^[a-zA-Z0-9._%+-]+@kpriet\.ac\.in$/;
        if (!kprietPattern.test(email)) {
            emailError.innerHTML = "Enter a valid KPRIET Email (@kpriet.ac.in)";
            valid = false;
        }
    } else if (customerType === "guest") {
        const standardEmailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!standardEmailPattern.test(email)) {
            emailError.innerHTML = "Enter a valid email address";
            valid = false;
        }
    }

    if (password === "") {
        passwordError.innerHTML = "Password is required";
        valid = false;
    } else if (password.length < 8) {
        passwordError.innerHTML = "Password must contain at least 8 characters";
        valid = false;
    }

    if (valid) {
        const destinations = {
            student: "../student/dashboard.html",
            faculty: "../customer/menu.html",
            guest: "../customer/menu.html"
        };

        window.location.href = destinations[customerType];
    }
});
