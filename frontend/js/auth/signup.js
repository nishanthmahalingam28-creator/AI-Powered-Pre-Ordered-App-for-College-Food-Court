const customerTypeSelect = document.getElementById("customerType");
const emailLabel = document.getElementById("emailLabel");
const emailInput = document.getElementById("email");
const fullNameInput = document.getElementById("fullName");
const passwordInput = document.getElementById("password");
const confirmPasswordInput = document.getElementById("confirmPassword");
const termsCheckbox = document.getElementById("terms");
const identityContainer = document.getElementById("identityContainer");
const identityLabel = document.getElementById("identityLabel");
const identityInput = document.getElementById("identityInput");
const identityError = document.getElementById("identityError");
const mobileNumberInput = document.getElementById("mobileNumber");
const sendOtpBtn = document.getElementById("sendOtpBtn");
const otpContainer = document.getElementById("otpContainer");
const otpInput = document.getElementById("otpInput");
const verifyOtpBtn = document.getElementById("verifyOtpBtn");
const mobileError = document.getElementById("mobileError");
const otpError = document.getElementById("otpError");
const otpSuccess = document.getElementById("otpSuccess");

let generatedOtp = null;
let isOtpVerified = false;

customerTypeSelect.addEventListener("change", function () {
    identityError.innerHTML = "";
    identityInput.value = "";

    if (this.value === "guest") {
        emailLabel.innerText = "Email ID";
        emailInput.placeholder = "example@gmail.com";
        identityContainer.classList.add("hidden");
    } else if (this.value === "faculty") {
        emailLabel.innerText = "Institute Email ID";
        emailInput.placeholder = "example@kpriet.ac.in";
        identityContainer.classList.remove("hidden");
        identityLabel.innerText = "Faculty ID";
        identityInput.placeholder = "e.g. KPRFAC102";
    } else {
        emailLabel.innerText = "Institute Email ID";
        emailInput.placeholder = "example@kpriet.ac.in";
        identityContainer.classList.remove("hidden");
        identityLabel.innerText = "Roll Number";
        identityInput.placeholder = "e.g. 21CS001";
    }
    document.getElementById("emailError").innerHTML = "";
});

sendOtpBtn.addEventListener("click", function () {
    const mobileVal = mobileNumberInput.value.trim();
    const phonePattern = /^[6-9]\d{9}$/;

    mobileError.innerHTML = "";
    otpSuccess.innerHTML = "";
    otpError.innerHTML = "";

    if (!phonePattern.test(mobileVal)) {
        mobileError.innerHTML = "Enter a valid 10-digit mobile number";
        return;
    }

    generatedOtp = Math.floor(1000 + Math.random() * 9000).toString();
    otpContainer.classList.remove("hidden");
    alert("Your OTP for registration is: " + generatedOtp);
    otpSuccess.innerHTML = "OTP sent successfully to +91 " + mobileVal;
});

verifyOtpBtn.addEventListener("click", function () {
    const enteredOtp = otpInput.value.trim();
    otpError.innerHTML = "";
    otpSuccess.innerHTML = "";

    if (enteredOtp === "") {
        otpError.innerHTML = "Please enter the OTP";
        return;
    }

    if (enteredOtp === generatedOtp) {
        isOtpVerified = true;
        otpSuccess.innerHTML = "Mobile number verified successfully! ✓";
        mobileNumberInput.disabled = true;
        sendOtpBtn.disabled = true;
        sendOtpBtn.classList.add("opacity-50", "cursor-not-allowed");
        verifyOtpBtn.disabled = true;
        verifyOtpBtn.classList.add("opacity-50", "cursor-not-allowed");
        otpInput.disabled = true;
    } else {
        otpError.innerHTML = "Invalid OTP. Please try again.";
    }
});

document.getElementById("signupForm").addEventListener("submit", function (event) {
    event.preventDefault();

    const fullName = fullNameInput.value.trim();
    const email = emailInput.value.trim();
    const password = passwordInput.value.trim();
    const confirmPassword = confirmPasswordInput.value.trim();
    const customerType = customerTypeSelect.value;
    const identityValue = identityInput.value.trim();
    const mobileVal = mobileNumberInput.value.trim();

    document.getElementById("nameError").innerHTML = "";
    document.getElementById("emailError").innerHTML = "";
    document.getElementById("passwordError").innerHTML = "";
    document.getElementById("confirmPasswordError").innerHTML = "";
    document.getElementById("termsError").innerHTML = "";
    identityError.innerHTML = "";
    mobileError.innerHTML = "";

    let valid = true;

    if (fullName === "") {
        document.getElementById("nameError").innerHTML = "Full name is required";
        valid = false;
    }

    if (customerType === "student" && identityValue === "") {
        identityError.innerHTML = "Roll number is required";
        valid = false;
    } else if (customerType === "faculty" && identityValue === "") {
        identityError.innerHTML = "Faculty ID is required";
        valid = false;
    }

    if (mobileVal === "") {
        mobileError.innerHTML = "Mobile number is required";
        valid = false;
    } else if (!isOtpVerified) {
        mobileError.innerHTML = "Please verify your mobile number with OTP";
        valid = false;
    }

    if (email === "") {
        document.getElementById("emailError").innerHTML = "Email is required";
        valid = false;
    } else if (customerType === "student" || customerType === "faculty") {
        const kprietPattern = /^[a-zA-Z0-9._%+-]+@kpriet\.ac\.in$/;
        if (!kprietPattern.test(email)) {
            document.getElementById("emailError").innerHTML = "Enter a valid KPRIET Email (@kpriet.ac.in)";
            valid = false;
        }
    } else if (customerType === "guest") {
        const standardEmailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!standardEmailPattern.test(email)) {
            document.getElementById("emailError").innerHTML = "Enter a valid email address";
            valid = false;
        }
    }

    if (password === "") {
        document.getElementById("passwordError").innerHTML = "Password is required";
        valid = false;
    } else if (password.length < 8) {
        document.getElementById("passwordError").innerHTML = "Password must contain at least 8 characters";
        valid = false;
    }

    if (confirmPassword === "") {
        document.getElementById("confirmPasswordError").innerHTML = "Please confirm your password";
        valid = false;
    } else if (password !== confirmPassword) {
        document.getElementById("confirmPasswordError").innerHTML = "Passwords do not match";
        valid = false;
    }

    if (!termsCheckbox.checked) {
        document.getElementById("termsError").innerHTML = "You must agree to the terms";
        valid = false;
    }

    if (valid) {
        window.location.href = "login.html";
    }
});
