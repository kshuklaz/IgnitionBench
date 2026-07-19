// Theme toggle: dark is the baseline, light overrides via
// :root[data-theme="light"]. The choice persists in localStorage and
// defaults to the system preference (an inline snippet in <head> applies
// it before first paint). JS-drawn surfaces listen for "themechange".

const KEY = "ib-theme";

function current() {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function swapLogos() {
  document.querySelectorAll("img[data-logo]").forEach((img) => {
    const dark = img.dataset.logo;
    img.src = current() === "light" ? dark.replace(/\.png$/, "-black.png") : dark;
  });
}

function apply(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(KEY, theme);
  const btn = document.getElementById("themeToggle");
  if (btn) {
    btn.textContent = theme === "light" ? "☾" : "☀";
    btn.title = theme === "light" ? "Switch to dark mode" : "Switch to light mode";
  }
  swapLogos();
  window.dispatchEvent(new CustomEvent("themechange"));
}

// colour of a CSS custom property, for canvas / WebGL drawing
window.ibColor = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
window.ibColorRGB = (name) => {
  const v = window.ibColor(name);
  return [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16));
};

document.getElementById("themeToggle")?.addEventListener("click", () =>
  apply(current() === "light" ? "dark" : "light"));
apply(current());
