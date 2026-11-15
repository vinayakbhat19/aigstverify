// Cursor-driven parallax for the backdrop, tilt and sheen for glass panels.
(function () {
    const root = document.documentElement;
    const photo = document.querySelector(".scene__photo");
    const tilters = Array.from(document.querySelectorAll("[data-tilt]"));
    const sheens = Array.from(document.querySelectorAll(".glass--sheen"));
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const finePointer = window.matchMedia("(pointer: fine)").matches;

    // Sheen tracking is cheap and works on any pointer.
    window.addEventListener("pointermove", (event) => {
        for (const el of sheens) {
            const box = el.getBoundingClientRect();
            el.style.setProperty("--mx", `${event.clientX - box.left}px`);
            el.style.setProperty("--my", `${event.clientY - box.top}px`);
            el.style.setProperty("--sheen", "1");
        }
    }, { passive: true });

    document.addEventListener("pointerleave", () => {
        for (const el of sheens) el.style.setProperty("--sheen", "0");
    });

    if (reduced || !finePointer) return;

    let targetX = 0, targetY = 0, x = 0, y = 0, running = false;

    window.addEventListener("pointermove", (event) => {
        targetX = event.clientX / window.innerWidth - 0.5;   // -0.5 .. 0.5
        targetY = event.clientY / window.innerHeight - 0.5;
        if (!running) { running = true; requestAnimationFrame(step); }
    }, { passive: true });

    document.addEventListener("pointerleave", () => {
        targetX = 0; targetY = 0;
        if (!running) { running = true; requestAnimationFrame(step); }
    });

    function step() {
        // Ease toward the cursor so the scene drifts rather than snaps.
        x += (targetX - x) * 0.08;
        y += (targetY - y) * 0.08;
        if (photo) {
            photo.style.setProperty("--px", `${(-x * 36).toFixed(2)}px`);
            photo.style.setProperty("--py", `${(-y * 24).toFixed(2)}px`);
        }
        for (const el of tilters) {
            el.style.setProperty("--ry", `${(x * 7).toFixed(2)}deg`);
            el.style.setProperty("--rx", `${(-y * 7).toFixed(2)}deg`);
        }
        if (Math.abs(targetX - x) > 0.0005 || Math.abs(targetY - y) > 0.0005) {
            requestAnimationFrame(step);
        } else {
            running = false;
        }
    }

    root.classList.add("has-motion");
})();
