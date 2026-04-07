document.addEventListener("DOMContentLoaded", () => {
    // Intersection Observer for scroll tips
    const tips = document.querySelectorAll(".scroll-tip");
    
    if (tips.length > 0) {
        const observer = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("visible");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        
        tips.forEach(tip => {
            observer.observe(tip);
        });
    }
});
