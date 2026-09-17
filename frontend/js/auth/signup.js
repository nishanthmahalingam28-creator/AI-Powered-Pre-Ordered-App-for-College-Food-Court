const API_BASE_URL = window.FOOD_COURT_API_BASE;

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
            otpSuccess.innerHTML = `OTP sent to +91 ${mobileVal}. ${data.demo_otp ? '(Dev OTP: <strong>' + data.demo_otp + '</strong>)' : ''}`;
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

// Real-time input listeners to clear errors on typing
[fullNameInput, emailInput, passwordInput, confirmPasswordInput, identityInput].forEach(inputEl => {
    if (inputEl) {
        inputEl.addEventListener("input", () => {
            const errId = inputEl.id === "identityInput" ? "identityError" : `${inputEl.id}Error`;
            const errEl = document.getElementById(errId);
            if (errEl) errEl.innerHTML = "";
        });
    }
});

document.getElementById("signupForm").addEventListener("submit", async function (event) {
    event.preventDefault();

    const fullName = fullNameInput.value.trim();
    const email = emailInput.value.trim().toLowerCase();
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
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

    // 1. Full Name Validation
    const namePattern = /^[a-zA-Z\s'.-]{2,50}$/;
    if (!fullName) {
        document.getElementById("nameError").innerHTML = "Full name is required.";
        valid = false;
    } else if (fullName.length < 2) {
        document.getElementById("nameError").innerHTML = "Full name must contain at least 2 characters.";
        valid = false;
    } else if (!namePattern.test(fullName)) {
        document.getElementById("nameError").innerHTML = "Full name can only contain letters, spaces, hyphens, and apostrophes.";
        valid = false;
    }

    // 2. Persona Identifier Validation
    if (customerType === "student" && !identityValue) {
        identityError.innerHTML = "Roll number is required for students.";
        valid = false;
    } else if (customerType === "faculty" && !identityValue) {
        identityError.innerHTML = "Faculty ID is required for faculty members.";
        valid = false;
    }

    // 3. Mobile & OTP Verification Validation
    if (!mobileVal) {
        mobileError.innerHTML = "Mobile number is required.";
        valid = false;
    } else if (!isOtpVerified) {
        mobileError.innerHTML = "Please verify your mobile number with OTP before registering.";
        valid = false;
    }

    // 4. Email Format Validation
    if (!email) {
        document.getElementById("emailError").innerHTML = "Email address is required.";
        valid = false;
    } else if (customerType === "student" || customerType === "faculty") {
        const kprietPattern = /^[a-zA-Z0-9._%+-]+@kpriet\.ac\.in$/i;
        if (!kprietPattern.test(email)) {
            document.getElementById("emailError").innerHTML = "Enter a valid KPRIET institutional email (@kpriet.ac.in).";
            valid = false;
        }
    } else if (customerType === "guest") {
        const standardEmailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!standardEmailPattern.test(email)) {
            document.getElementById("emailError").innerHTML = "Enter a valid email address.";
            valid = false;
        }
    }

    // 5. Password Strength Validation (min 8 chars, at least 1 letter and 1 number)
    const hasLetter = /[a-zA-Z]/.test(password);
    const hasNumber = /\d/.test(password);
    if (!password) {
        document.getElementById("passwordError").innerHTML = "Password is required.";
        valid = false;
    } else if (password.length < 8) {
        document.getElementById("passwordError").innerHTML = "Password must contain at least 8 characters.";
        valid = false;
    } else if (!hasLetter || !hasNumber) {
        document.getElementById("passwordError").innerHTML = "Password must contain both letters and numbers.";
        valid = false;
    }

    // 6. Confirm Password Matching Validation
    if (!confirmPassword) {
        document.getElementById("confirmPasswordError").innerHTML = "Please confirm your password.";
        valid = false;
    } else if (password !== confirmPassword) {
        document.getElementById("confirmPasswordError").innerHTML = "Passwords do not match.";
        valid = false;
    }

    // 7. Terms & Conditions
    if (!termsCheckbox.checked) {
        document.getElementById("termsError").innerHTML = "You must agree to the Terms of Service.";
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
            credentials: 'include',
            body: JSON.stringify({
                fullName,
                email,
                password,
                confirmPassword,
                customerType,
                identifier: identityValue,
                mobile: mobileVal
            })
        });
        const data = await res.json();

        if (res.ok && data.success) {
            if (data.user) {
                sessionStorage.setItem("foodCourtUser", JSON.stringify(data.user));
            }
            alert("Account registered successfully! Entering KPR Food Court...");
            window.location.href = data.redirect || "../customer/dashboard.html";
        } else {
            const msg = data.message || "Registration failed.";
            if (res.status === 409 || msg.toLowerCase().includes("email")) {
                document.getElementById("emailError").innerHTML = msg;
            } else if (msg.toLowerCase().includes("mobile")) {
                mobileError.innerHTML = msg;
            } else if (msg.toLowerCase().includes("password")) {
                document.getElementById("passwordError").innerHTML = msg;
            } else if (msg.toLowerCase().includes("name")) {
                document.getElementById("nameError").innerHTML = msg;
            } else {
                document.getElementById("emailError").innerHTML = msg;
            }
        }
    } catch (e) {
        document.getElementById("emailError").innerHTML = "Connection error. Ensure the backend API server is running.";
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
});
