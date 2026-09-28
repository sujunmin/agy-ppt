"use strict";

const carousels = Array.from(document.querySelectorAll("[data-carousel]"));
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const autoplayDelay = 4500;
const visibility = new Map();
let primaryCarousel = null;
let autoplayTimer = 0;

function clearAutoplay() {
  window.clearTimeout(autoplayTimer);
  autoplayTimer = 0;
}

function setPrimaryCarousel() {
  const visible = carousels
    .filter((carousel) => (visibility.get(carousel) || 0) > 0)
    .map((carousel) => {
      const rect = carousel.getBoundingClientRect();
      return {
        carousel,
        ratio: visibility.get(carousel),
        distance: Math.abs((rect.top + rect.bottom) / 2 - window.innerHeight / 2),
      };
    })
    .sort((a, b) => b.ratio - a.ratio || a.distance - b.distance);
  primaryCarousel = visible[0]?.carousel || null;
  scheduleAutoplay();
}

function canAutoplay(carousel) {
  return carousel === primaryCarousel
    && !reduceMotion.matches
    && !document.hidden
    && carousel.dataset.hovered !== "true"
    && carousel.dataset.focused !== "true"
    && carousel.dataset.userPaused !== "true";
}

function scheduleAutoplay() {
  clearAutoplay();
  if (!primaryCarousel || !canAutoplay(primaryCarousel)) return;
  autoplayTimer = window.setTimeout(() => {
    showSlide(primaryCarousel, Number(primaryCarousel.dataset.activeSlide || 0) + 1, false);
    scheduleAutoplay();
  }, autoplayDelay);
}

function showSlide(carousel, requestedIndex, manual = true) {
  const dots = Array.from(carousel.querySelectorAll("[data-slide-to]"));
  if (!dots.length) return;
  const index = ((requestedIndex % dots.length) + dots.length) % dots.length;
  const selected = dots[index];
  const image = carousel.querySelector("[data-carousel-image]");
  const slide = carousel.querySelector(".showcase-visual[aria-roledescription='slide']");
  const position = carousel.querySelector("[data-position]");
  const announcement = carousel.querySelector("[data-slide-announcement]");
  const isTraditionalChinese = document.documentElement.lang === "zh-Hant";

  carousel.dataset.activeSlide = String(index);
  image.src = selected.dataset.src;
  image.alt = selected.dataset.alt;
  slide.setAttribute("aria-label", isTraditionalChinese
    ? `第 ${index + 1} 張，共 ${dots.length} 張`
    : `Slide ${index + 1} of ${dots.length}`);
  position.textContent = String(index + 1).padStart(2, "0");
  if (manual) {
    const exampleName = carousel.getAttribute("aria-label");
    announcement.textContent = isTraditionalChinese
      ? `${exampleName}：第 ${index + 1} 張，共 ${dots.length} 張`
      : `${exampleName}: slide ${index + 1} of ${dots.length}`;
  }
  dots.forEach((dot, dotIndex) => {
    const active = dotIndex === index;
    dot.classList.toggle("is-active", active);
    dot.tabIndex = active ? 0 : -1;
    if (active) dot.setAttribute("aria-current", "true");
    else dot.removeAttribute("aria-current");
  });

  if (manual) scheduleAutoplay();
  image.classList.remove("slide-enter");
  void image.offsetWidth;
  image.classList.add("slide-enter");
}

function updateAutoplayControl(carousel) {
  const button = carousel.querySelector("[data-autoplay-toggle]");
  const paused = carousel.dataset.userPaused === "true";
  const isTraditionalChinese = document.documentElement.lang === "zh-Hant";
  button.disabled = reduceMotion.matches;
  button.setAttribute("aria-label", reduceMotion.matches
    ? (isTraditionalChinese ? "已依減少動態效果設定停用自動播放" : "Autoplay disabled by reduced-motion preference")
    : paused
      ? (isTraditionalChinese ? "開始自動播放" : "Start automatic slide show")
      : (isTraditionalChinese ? "暫停自動播放" : "Pause automatic slide show"));
  button.querySelector("span").textContent = reduceMotion.matches ? "–" : paused ? "▶" : "Ⅱ";
}

function setVisibility(carousel, ratio) {
  visibility.set(carousel, ratio);
  setPrimaryCarousel();
}

for (const carousel of carousels) {
  carousel.dataset.activeSlide = "0";
  carousel.dataset.userPaused = "false";
  updateAutoplayControl(carousel);

  carousel.querySelector("[data-previous]").addEventListener("click", () => {
    showSlide(carousel, Number(carousel.dataset.activeSlide) - 1);
  });
  carousel.querySelector("[data-next]").addEventListener("click", () => {
    showSlide(carousel, Number(carousel.dataset.activeSlide) + 1);
  });
  carousel.querySelectorAll("[data-slide-to]").forEach((dot) => {
    dot.addEventListener("click", () => showSlide(carousel, Number(dot.dataset.slideTo)));
  });
  carousel.querySelector("[data-autoplay-toggle]").addEventListener("click", () => {
    carousel.dataset.userPaused = carousel.dataset.userPaused === "true" ? "false" : "true";
    updateAutoplayControl(carousel);
    scheduleAutoplay();
  });
  carousel.addEventListener("pointerenter", () => {
    carousel.dataset.hovered = "true";
    scheduleAutoplay();
  });
  carousel.addEventListener("pointerleave", () => {
    carousel.dataset.hovered = "false";
    scheduleAutoplay();
  });
  carousel.addEventListener("focusin", () => {
    carousel.dataset.focused = "true";
    scheduleAutoplay();
  });
  carousel.addEventListener("focusout", (event) => {
    if (!carousel.contains(event.relatedTarget)) {
      carousel.dataset.focused = "false";
      scheduleAutoplay();
    }
  });
  carousel.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const current = Number(carousel.dataset.activeSlide || 0);
    if (event.key === "ArrowRight") {
      event.preventDefault();
      showSlide(carousel, current + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      showSlide(carousel, current - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      showSlide(carousel, 0);
    } else if (event.key === "End") {
      event.preventDefault();
      showSlide(carousel, 3);
    }
  });

  let swipeStart = null;
  const stage = carousel.querySelector(".showcase-visual");
  stage.addEventListener("pointerdown", (event) => {
    if (event.pointerType !== "touch" || event.target.closest("button")) return;
    swipeStart = { x: event.clientX, y: event.clientY };
  });
  stage.addEventListener("pointerup", (event) => {
    if (!swipeStart || event.target.closest("button")) {
      swipeStart = null;
      return;
    }
    const deltaX = event.clientX - swipeStart.x;
    const deltaY = event.clientY - swipeStart.y;
    swipeStart = null;
    if (Math.abs(deltaX) > 48 && Math.abs(deltaX) > Math.abs(deltaY) * 1.25) {
      showSlide(carousel, Number(carousel.dataset.activeSlide) + (deltaX < 0 ? 1 : -1));
    }
  });
  stage.addEventListener("pointercancel", () => { swipeStart = null; });
}

if ("IntersectionObserver" in window) {
  const carouselObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      setVisibility(entry.target, entry.isIntersecting && entry.intersectionRatio >= 0.25 ? entry.intersectionRatio : 0);
    }
  }, { threshold: [0, 0.1, 0.25, 0.5, 0.75, 1] });
  carousels.forEach((carousel) => carouselObserver.observe(carousel));
} else {
  const updateVisibility = () => {
    for (const carousel of carousels) {
      const rect = carousel.getBoundingClientRect();
      const visibleWidth = Math.max(0, Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0));
      const visibleHeight = Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0));
      const ratio = rect.width && rect.height ? (visibleWidth * visibleHeight) / (rect.width * rect.height) : 0;
      setVisibility(carousel, ratio >= 0.25 ? ratio : 0);
    }
  };
  window.addEventListener("scroll", updateVisibility, { passive: true });
  window.addEventListener("resize", updateVisibility);
  updateVisibility();
}

reduceMotion.addEventListener?.("change", () => {
  carousels.forEach(updateAutoplayControl);
  scheduleAutoplay();
});
document.addEventListener("visibilitychange", scheduleAutoplay);

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const status = button.closest(".code-card")?.querySelector(".copy-status");
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      if (status) {
        status.textContent = document.documentElement.lang === "zh-Hant"
          ? "指令已複製。"
          : "Commands copied.";
      }
    } catch {
      if (status) {
        status.textContent = document.documentElement.lang === "zh-Hant"
          ? "請選取上方指令並手動複製。"
          : "Select and copy the commands above.";
      }
    }
  });
});
