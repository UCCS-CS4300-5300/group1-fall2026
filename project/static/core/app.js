import { initializeApp } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js";
import {
  createUserWithEmailAndPassword,
  getAuth,
  signInWithEmailAndPassword,
} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";

// These values tell this page which Firebase project handles sign-in.
const firebaseConfig = {
  apiKey: "AIzaSyBMxtag5VrtQUpiqgifsQqrU6qkFW08jI0",
  authDomain: "repkin-firebase.firebaseapp.com",
  projectId: "repkin-firebase",
  storageBucket: "repkin-firebase.firebasestorage.app",
  messagingSenderId: "965206407298",
  appId: "1:965206407298:web:691a5e46be17e8712a5c9b",
  measurementId: "G-YJHJ3N8J1T"
};

// Connect this page to Firebase's sign-in service.
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

document.querySelectorAll("[data-firebase-auth]").forEach((form) => {
  const isSignUp = form.dataset.firebaseAuth === "signup";
  const errorMessage = document.getElementById(isSignUp ? "signup-error" : "login-error");
  const submitButton = form.querySelector("button[type='submit']");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorMessage.hidden = true;

    if (isSignUp && form.elements.password.value !== form.elements.passwordConfirm.value) {
      errorMessage.textContent = "The passwords do not match.";
      errorMessage.hidden = false;
      return;
    }

    submitButton.disabled = true;
    const csrfToken = form.querySelector("[name='csrfmiddlewaretoken']").value;
    try {
      const email = form.elements.email.value.trim();
      const password = form.elements.password.value;
      const { user } = isSignUp
        ? await createUserWithEmailAndPassword(auth, email, password)
        : await signInWithEmailAndPassword(auth, email, password);
      const response = await fetch(form.dataset.sessionUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          csrfmiddlewaretoken: csrfToken,
          idToken: await user.getIdToken(),
        }),
      });
      if (!response.ok) throw new Error("session-rejected");
      const result = await response.json();
      window.location.assign(result.redirectUrl);
    } catch (error) {
      console.error("Firebase authentication error:", error.code || error.message || "request-failed");
      errorMessage.textContent = isSignUp
        ? "Unable to create account. Check your details or try a different email."
        : "Unable to sign in. Check your email and password.";
      errorMessage.hidden = false;
    } finally {
      submitButton.disabled = false;
    }
  });
});