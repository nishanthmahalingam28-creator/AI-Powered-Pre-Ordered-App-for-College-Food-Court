const API_BASE_URL = window.FOOD_COURT_API_BASE || 'http://127.0.0.1:5000/api';

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

sendOtpBtn.addEventListener("click", async function () {
    const mobileVal = mobileNumberInput.value.trim();
    const phonePattern = /^[6-9]\d{9}$/;

    mobileError.innerHTML = "";
    otpSuccess.innerHTML = "";
    otpError.innerHTML = "";

    if (!phonePattern.test(mobileVal)) {
        mobileError.innerHTML = "Enter a valid 10-digit mobile number";
        return;
    }

    sendOtpBtn.disabled = true;
    sendOtpBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Sending...';

    try {
        const res = await fetch(`${API_BASE_URL}/auth/otp/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mobile: mobileVal, purpose: 'signup' })
        });
        const data = await res.json();

        if (res.ok && data.success) {
            otpContainer.classList.remove("hidden");
            otpSuccess.innerHTML = `OTP sent to +91 ${mobileVal}. ${data.demo_otp ? '(Demo OTP: <strong>' + data.demo_otp + '</strong>)' : ''}`;
            if (data.demo_otp) {
                otpInput.value = data.demo_otp;
            }
        } else {
            mobileError.innerHTML = data.message || "Failed to dispatch OTP.";
        }
    } catch (e) {
        mobileError.innerHTML = "Unable to connect to OTP service.";
    } finally {
        sendOtpBtn.disabled = false;
        sendOtpBtn.innerHTML = 'Send OTP';
    }
});

verifyOtpBtn.addEventListener("click", async function () {
    const enteredOtp = otpInput.value.trim();
    const mobileVal = mobileNumberInput.value.trim();

    otpError.innerHTML = "";
    otpSuccess.innerHTML = "";

    if (enteredOtp === "") {
        otpError.innerHTML = "Please enter the OTP code";
        return;
    }

    verifyOtpBtn.disabled = true;
    verifyOtpBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-1"></i> Verifying...';

    try {
        const res = await fetch(`${API_BASE_URL}/auth/otp/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mobile: mobileVal, code: enteredOtp, purpose: 'signup' })
        });
        const data = await res.json();

        if (res.ok && data.success) {
            isOtpVerified = true;
            otpSuccess.innerHTML = "Mobile number verified successfully! ✓";
            mobileNumberInput.disabled = true;
            sendOtpBtn.disabled = true;
            sendOtpBtn.classList.add("opacity-50", "cursor-not-allowed");
            verifyOtpBtn.disabled = true;
            verifyOtpBtn.classList.add("opacity-50", "cursor-not-allowed");
            otpInput.disabled = true;
        } else {
            otpError.innerHTML = data.message || "Invalid OTP code.";
        }
    } catch (e) {
        otpError.innerHTML = "Unable to verify OTP.";
    } finally {
        if (!isOtpVerified) {
            verifyOtpBtn.disabled = false;
            verifyOtpBtn.innerHTML = 'Verify OTP';
        }
    }
});

mobileNumberInput.addEventListener("input", function () {
    if (isOtpVerified) {
        isOtpVerified = false;
        sendOtpBtn.disabled = false;
        sendOtpBtn.classList.remove("opacity-50", "cursor-not-allowed");
        verifyOtpBtn.disabled = false;
        verifyOtpBtn.classList.remove("opacity-50", "cursor-not-allowed");
        otpInput.disabled = false;
        otpInput.value = "";
        otpSuccess.innerHTML = "";
        mobileError.innerHTML = "Mobile number was modified. Please re-verify with OTP.";
    }
});

document.getElementById("signupForm").addEventListener("submit", async function (event) {
    event.preventDefault();

    const fullName = fullNameInput.value.trim();
    const email = emailInput.value.trim();
    const password = passwordInput.value.trim();
    const confirmPassword = confirmPasswordInput.value.trim();
    const customerType = customerTypeSelect.value;
    const identityValue = identityInput.value.trim();
    const mobileVal = mobileNumberInput.value.trim();
    const submitBtn = this.querySelector('button[type="submit"]');

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

    if (!valid) return;

    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Registering Account...</span><i class="fa-solid fa-spinner fa-spin ml-2"></i>';

    try {
        const res = await fetch(`${API_BASE_URL}/auth/customer/signup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fullName,
                email,
                password,
                customerType,
                identifier: identityValue,
                mobile: mobileVal
            })
        });
        const data = await res.json();

        if (res.ok && data.success) {
            alert("Account registered successfully! Please log in.");
            window.location.href = data.redirect || "login.html";
        } else {
            document.getElementById("emailError").innerHTML = data.message || "Registration failed.";
        }
    } catch (e) {
        document.getElementById("emailError").innerHTML = "Connection error. Ensure the Flask API is running.";
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
});
