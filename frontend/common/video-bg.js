/*
 * SecureGate live background
 * Lightweight canvas particle network used behind the active portals.
 */
(function () {
    class ParticleNetwork {
        constructor(canvasId) {
            this.canvas = document.getElementById(canvasId);
            if (!this.canvas) return;

            this.ctx = this.canvas.getContext('2d');
            this.particles = [];
            this.animationFrame = null;
            this.mouseX = -1000;
            this.mouseY = -1000;
            this.maxDist = 145;
            this.dpr = Math.min(window.devicePixelRatio || 1, 2);
            this.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            this.pointerFine = window.matchMedia('(pointer: fine)').matches;
            const styles = getComputedStyle(document.body);
            const accentRgb = styles.getPropertyValue('--accent-rgb').trim() || '96, 165, 250';
            const successRgb = styles.getPropertyValue('--success-rgb').trim() || '52, 211, 153';
            this.colors = {
                node: `rgba(${accentRgb}, 0.46)`,
                line: `rgba(${accentRgb}, `,
                accent: `rgba(${successRgb}, 0.35)`
            };

            this.resize = this.resize.bind(this);
            this.animate = this.animate.bind(this);
            this.handlePointerMove = this.handlePointerMove.bind(this);
            this.handlePointerLeave = this.handlePointerLeave.bind(this);
            this.handleVisibilityChange = this.handleVisibilityChange.bind(this);

            this.resize();
            this.bindEvents();
            this.init();

            if (this.prefersReducedMotion) {
                this.draw();
            } else {
                this.start();
            }
        }

        bindEvents() {
            window.addEventListener('resize', this.resize, { passive: true });
            document.addEventListener('visibilitychange', this.handleVisibilityChange);

            if (this.pointerFine && !this.prefersReducedMotion) {
                document.addEventListener('mousemove', this.handlePointerMove, { passive: true });
                document.addEventListener('mouseleave', this.handlePointerLeave, { passive: true });
            }
        }

        resize() {
            const width = window.innerWidth;
            const height = window.innerHeight;
            this.dpr = Math.min(window.devicePixelRatio || 1, 2);
            this.canvas.width = Math.floor(width * this.dpr);
            this.canvas.height = Math.floor(height * this.dpr);
            this.canvas.style.width = `${width}px`;
            this.canvas.style.height = `${height}px`;
            this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
            this.init();
            this.draw();
        }

        init() {
            const area = window.innerWidth * window.innerHeight;
            const count = Math.min(Math.max(Math.floor(area / 22000), 28), 78);
            this.particles = Array.from({ length: count }, () => ({
                x: Math.random() * window.innerWidth,
                y: Math.random() * window.innerHeight,
                vx: (Math.random() - 0.5) * 0.32,
                vy: (Math.random() - 0.5) * 0.32,
                size: Math.random() * 1.6 + 0.6
            }));
        }

        start() {
            if (this.animationFrame || document.hidden) return;
            this.animationFrame = requestAnimationFrame(this.animate);
        }

        stop() {
            if (!this.animationFrame) return;
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }

        handlePointerMove(event) {
            this.mouseX = event.clientX;
            this.mouseY = event.clientY;
        }

        handlePointerLeave() {
            this.mouseX = -1000;
            this.mouseY = -1000;
        }

        handleVisibilityChange() {
            if (document.hidden) {
                this.stop();
            } else if (!this.prefersReducedMotion) {
                this.start();
            }
        }

        animate() {
            this.animationFrame = null;
            this.draw();
            this.update();
            this.start();
        }

        draw() {
            const width = window.innerWidth;
            const height = window.innerHeight;
            this.ctx.clearRect(0, 0, width, height);

            for (let i = 0; i < this.particles.length; i += 1) {
                const current = this.particles[i];

                for (let j = i + 1; j < this.particles.length; j += 1) {
                    this.drawConnection(current, this.particles[j]);
                }

                if (this.pointerFine && !this.prefersReducedMotion) {
                    this.drawMouseConnection(current);
                }

                this.ctx.beginPath();
                this.ctx.fillStyle = i % 9 === 0 ? this.colors.accent : this.colors.node;
                this.ctx.arc(current.x, current.y, current.size, 0, Math.PI * 2);
                this.ctx.fill();
            }
        }

        drawConnection(a, b) {
            const dx = a.x - b.x;
            const dy = a.y - b.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance >= this.maxDist) return;

            const alpha = (1 - distance / this.maxDist) * 0.34;
            this.ctx.beginPath();
            this.ctx.strokeStyle = `${this.colors.line}${alpha})`;
            this.ctx.lineWidth = 1;
            this.ctx.moveTo(a.x, a.y);
            this.ctx.lineTo(b.x, b.y);
            this.ctx.stroke();
        }

        drawMouseConnection(particle) {
            const dx = particle.x - this.mouseX;
            const dy = particle.y - this.mouseY;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance <= 0 || distance >= this.maxDist) return;

            this.ctx.beginPath();
            this.ctx.strokeStyle = `${this.colors.line}${(1 - distance / this.maxDist) * 0.45})`;
            this.ctx.lineWidth = 1;
            this.ctx.moveTo(particle.x, particle.y);
            this.ctx.lineTo(this.mouseX, this.mouseY);
            this.ctx.stroke();
        }

        update() {
            const width = window.innerWidth;
            const height = window.innerHeight;

            for (const particle of this.particles) {
                particle.x += particle.vx;
                particle.y += particle.vy;

                if (particle.x < 0 || particle.x > width) particle.vx *= -1;
                if (particle.y < 0 || particle.y > height) particle.vy *= -1;

                particle.x = Math.max(0, Math.min(width, particle.x));
                particle.y = Math.max(0, Math.min(height, particle.y));
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('particleCanvas')) {
            window.secureGateLiveBackground = new ParticleNetwork('particleCanvas');
        }
    });
}());
