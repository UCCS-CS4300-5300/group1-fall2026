import { initializeApp } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js";
import { getAuth, signInWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";

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

const loginForm = document.querySelector("#firebase-login-form");
const errorMessage = document.querySelector("#login-error");
const submitButton = loginForm.querySelector("button[type='submit']");

// When the form is sent, have Firebase check the password and Django remember the login.
loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.hidden = true;
  submitButton.disabled = true;

  // Include Django's safety code so another site cannot fake this request.
  const csrfToken = loginForm.querySelector("[name='csrfmiddlewaretoken']").value;
  try {
    const { user } = await signInWithEmailAndPassword(
      auth,
      loginForm.elements.email.value.trim(),
      loginForm.elements.password.value,
    );
    // Send Firebase's proof to Django; the password itself stays with Firebase.
    const response = await fetch(loginForm.dataset.sessionUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ csrfmiddlewaretoken: csrfToken, idToken: await user.getIdToken() }),
    });
    if (!response.ok) throw new Error();
    window.location.assign("/");
  } catch (error) {
    console.error("Sign-in error code:", error.code || "request-failed");
    errorMessage.textContent = "Unable to sign in. Check your email and password.";
    errorMessage.hidden = false;
  } finally {
    submitButton.disabled = false;
  }
});