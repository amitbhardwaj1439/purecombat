(function () {
  "use strict";
  document.documentElement.classList.remove("no-js");

  var WHATSAPP_NUMBER = "919728894872";
  var header = document.querySelector(".site-header");
  var toggle = document.querySelector(".nav-toggle");
  var navLinks = document.querySelectorAll(".nav-links a");

  /* Header background on scroll */
  function onScroll() {
    if (header) header.classList.toggle("is-solid", window.scrollY > 24);
  }
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* Mobile menu */
  function closeMenu() {
    document.body.classList.remove("nav-open");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }
  navLinks.forEach(function (a) { a.addEventListener("click", closeMenu); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeMenu(); });

  /* Active section highlighting (home page only) */
  var sectionLinks = Array.prototype.filter.call(navLinks, function (a) {
    var h = a.getAttribute("href") || "";
    return h.indexOf("#") !== -1 && document.getElementById(h.split("#")[1]);
  });
  if (sectionLinks.length && "IntersectionObserver" in window) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var id = entry.target.id;
        sectionLinks.forEach(function (a) {
          a.classList.toggle("active", a.getAttribute("href").split("#")[1] === id);
        });
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    sectionLinks.forEach(function (a) {
      spy.observe(document.getElementById(a.getAttribute("href").split("#")[1]));
    });
  }

  /* Reveal on scroll */
  var reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add("in"); ro.unobserve(entry.target); }
      });
    }, { threshold: 0.12 });
    reveals.forEach(function (el) { ro.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("in"); });
  }

  /* Enquiry form -> WhatsApp */
  var form = document.getElementById("enquiryForm");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!form.checkValidity()) { form.reportValidity(); return; }
      var v = function (id) { return (document.getElementById(id).value || "").trim(); };
      var lines = [
        "New enquiry – PURECOMBAT",
        "",
        "Name: " + v("name"),
        "Phone: " + v("phone"),
        "Age: " + v("age"),
        "Program: " + v("program")
      ];
      if (v("goal")) lines.push("Goal: " + v("goal"));
      lines.push("", "Please get in touch with me.");
      window.open("https://wa.me/" + WHATSAPP_NUMBER + "?text=" + encodeURIComponent(lines.join("\n")), "_blank", "noopener");
    });
  }

  /* Footer year */
  var y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();
})();
