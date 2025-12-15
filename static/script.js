// This file assumes the Firebase initialization is done in a separate <script type="module"> block 
// in index.html, exposing necessary variables (window.auth, window.db, etc.).

document.addEventListener('DOMContentLoaded', () => {
    // --- REDIRECT URLS ---
    const USER_KEY = 'chatAppUser';
    const HOME_REDIRECT_URL = 'home/home.html'; 
    // UPDATED REDIRECT PATH for Mitra AI Assistant
    const MITRA_AI_REDIRECT_URL = 'MitraAI/mitra.html'; 

    // --- DOM Elements ---
    const tabBtns = document.querySelectorAll('.tab-btn');
    const errorContainer = document.getElementById('error-container');
    const loginBtn = document.getElementById('login-btn');
    const loginEmailInput = document.getElementById('login-email');
    const loginPasswordInput = document.getElementById('login-password');
    const googleLoginBtn = document.getElementById('google-login-btn');
    const mitraAiBtn = document.getElementById('mitra-ai-btn'); 
    const registerBtn = document.getElementById('register-btn');
    const registerNameInput = document.getElementById('register-name');
    const registerEmailInput = document.getElementById('register-email');
    const registerPasswordInput = document.getElementById('register-password');
    const registerConfirmPasswordInput = document.getElementById('register-confirm-password');

    // Check for global Firebase variables
    if (typeof window.auth === 'undefined') {
        // If the script runs before Firebase is fully loaded, this will alert the user.
        console.error("Firebase Auth or DB not initialized. Check index.html script block.");
    }
    
    // --- Utility/UI Functions ---

    function showError(message) {
        if (message) {
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
        } else {
            errorContainer.style.display = 'none';
        }
    }

    function switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add('active');

        // Hide all forms and show the selected one
        document.querySelectorAll('.form-container').forEach(form => form.classList.remove('active'));
        document.getElementById(`${tabName}-form`).classList.add('active');
        
        showError('');
    }
    
    /** Saves the user name to localStorage and redirects to the specified URL. */
    function completeLogin(user, redirectUrl) {
        // 1. Prioritize Firebase displayName 
        // 2. Fallback to extracting the name from the email
        const username = user.displayName || user.email.split('@')[0] || "Guest"; 
        
        // Save the derived username to localStorage
        localStorage.setItem(USER_KEY, username);
        
        // Redirect to the target page
        window.location.href = redirectUrl; 
    }

    // Function to save basic user data to Firestore
    async function saveUserToDB(user, fullName) {
        try {
            const nameToSave = fullName || user.displayName || user.email.split('@')[0] || 'User';

            await window.setDoc(window.doc(window.db, "users", user.uid), {
                uid: user.uid,
                email: user.email,
                name: nameToSave,
                createdAt: new Date(),
                authMethod: user.providerId || 'email'
            });
            console.log("User data saved to Firestore successfully.");
        } catch (e) {
            console.error("Error saving user data to Firestore:", e);
        }
    }


    // --- Auth Functions ---

    // Email/Password Login
    async function handleEmailLogin() {
        showError('');
        const email = loginEmailInput.value.trim();
        const password = loginPasswordInput.value;

        if (!email || !password) { return showError("Please enter both email and password."); }

        try {
            const userCredential = await window.signInWithEmailAndPassword(window.auth, email, password);
            console.log("Login Successful:", userCredential.user);
            completeLogin(userCredential.user, HOME_REDIRECT_URL); // Default redirect
            
        } catch (error) {
            console.error("Login Error:", error);
            let errorMessage = "Login failed. Please check your credentials.";
            if (error.code === 'auth/invalid-credential') { errorMessage = "Invalid email or password."; }
            showError(errorMessage);
        }
    }
    
    // Email/Password Registration
    async function handleEmailRegister() {
        showError('');
        const name = registerNameInput.value.trim();
        const email = registerEmailInput.value.trim();
        const password = registerPasswordInput.value;
        const confirmPassword = registerConfirmPasswordInput.value;

        if (!name || !email || !password || !confirmPassword) { return showError("All fields are required."); }
        if (password !== confirmPassword) { return showError("Passwords do not match."); }
        if (password.length < 6) { return showError("Password must be at least 6 characters long."); }

        try {
            const userCredential = await window.createUserWithEmailAndPassword(window.auth, email, password);
            const user = userCredential.user;
            
            // 1. Update the Firebase Auth User profile to set the displayName
            await window.updateProfile(user, { displayName: name });

            // 2. Save user data to Firestore
            await saveUserToDB(user, name);
            
            console.log("Registration Successful:", user);
            completeLogin(user, HOME_REDIRECT_URL); // Default redirect

        } catch (error) {
            console.error("Registration Error:", error);
            let errorMessage = "Registration failed.";
            if (error.code === 'auth/email-already-in-use') { errorMessage = "This email is already registered."; } 
            else if (error.code === 'auth/weak-password') { errorMessage = "The password is too weak. Choose a stronger one."; }
            showError(errorMessage);
        }
    }

    // Google Sign-In (Handles both Login and Register tabs)
    async function handleGoogleSignIn() {
        showError('');
        try {
            const result = await window.signInWithPopup(window.auth, window.googleProvider);
            const user = result.user;
            
            // If it's a new user, save initial data to Firestore
            if (user.metadata.creationTime === user.metadata.lastSignInTime) {
                await saveUserToDB(user, user.displayName);
            }

            console.log("Google Sign-In Successful:", user);
            completeLogin(user, HOME_REDIRECT_URL); // Default redirect

        } catch (error) {
            console.error("Google Sign-In Error:", error);
            let errorMessage = "Google sign-in failed.";
            if (error.code === 'auth/popup-closed-by-user') { errorMessage = "Sign-in popup closed. Please try again."; }
            showError(errorMessage);
        }
    }

    // Function to handle redirection to Mitra AI page
    function handleMitraAIRedirect() {
        showError(''); 
        // Direct link to the Mitra AI Chat application path
        window.location.href = MITRA_AI_REDIRECT_URL; 
    }


    // --- Event Listeners Initialization ---
    
    // Tab Switching Logic
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => switchTab(e.currentTarget.getAttribute('data-tab')));
    });

    // Login Form Submissions
    document.getElementById('login-btn').addEventListener('click', handleEmailLogin);
    document.getElementById('google-login-btn').addEventListener('click', handleGoogleSignIn);

    // MITRA AI BUTTON REDIRECT (Direct Redirection)
    if (mitraAiBtn) {
        mitraAiBtn.addEventListener('click', handleMitraAIRedirect);
    }
    
    // Register Form Submissions
    document.getElementById('register-btn').addEventListener('click', handleEmailRegister);
    document.getElementById('google-register-btn').addEventListener('click', handleGoogleSignIn); 


    // Check if user is already logged in and redirect on load
    if (localStorage.getItem(USER_KEY)) {
        console.log("User already logged in. Checking active session...");
        // In a real app, you would verify the Firebase auth state here. 
        // For this frontend-only logic, we assume the local storage key is sufficient
        // for redirection to the main app page.
        // window.location.href = HOME_REDIRECT_URL;
    }
});