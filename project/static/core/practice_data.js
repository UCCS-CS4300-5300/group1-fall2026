const form = document.querySelector("#practice-data-form");
const loadButton = document.querySelector("#load-practice-data");
const result = document.querySelector("#practice-result");

// Read this signed-in user's saved practice count and show the result.
async function loadPracticeData() {
  const response = await fetch(form.action, { credentials: "same-origin" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Unable to load the saved value.");
  result.textContent = data.practicePushups === null
    ? "No value has been saved yet."
    : `Saved sample: ${data.practicePushups} push-ups.`;
}

// Send the sample count to Django and show whether the save worked.
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button[type='submit']");
  button.disabled = true;
  result.textContent = "Saving...";
  try {
    const response = await fetch(form.action, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": form.querySelector("[name='csrfmiddlewaretoken']").value,
      },
      body: new URLSearchParams(new FormData(form)),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save the value.");
    result.textContent = `Saved sample: ${data.practicePushups} push-ups.`;
  } catch (error) {
    result.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

// Reload the saved count when the user presses the load button.
loadButton.addEventListener("click", async () => {
  loadButton.disabled = true;
  result.textContent = "Loading...";
  try {
    await loadPracticeData();
  } catch (error) {
    result.textContent = error.message;
  } finally {
    loadButton.disabled = false;
  }
});