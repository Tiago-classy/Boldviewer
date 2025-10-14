class ThumbnailLoader {
    constructor() {
        this.observer = null;
        this.loadingQueue = new Set();
        this.init();
    }

    init() {
        if ('IntersectionObserver' in window) {
            this.observer = new IntersectionObserver(
                (entries) => this.handleIntersection(entries),
                { rootMargin: '50px' }
            );
            this.observeThumbnails();
        } else {
            this.loadAllThumbnails();
        }
    }

    observeThumbnails() {
        document.querySelectorAll('.lazy-thumbnail').forEach(img => {
            this.observer.observe(img);
        });
    }

    handleIntersection(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                this.loadThumbnail(entry.target);
                this.observer.unobserve(entry.target);
            }
        });
    }

    async loadThumbnail(img) {
        const filename = img.closest('.file-thumbnail').dataset.filename;
        if (this.loadingQueue.has(filename)) return;
        
        this.loadingQueue.add(filename);
        const container = img.closest('.file-thumbnail');
        const icon = container.querySelector('.file-icon');
        
        try {
            if (icon) icon.classList.add('loading');
            
            const ready = await this.checkThumbnailReady(filename);
            
            if (ready) {
                this.showThumbnail(img, icon);
            } else {
                this.pollThumbnail(filename, img, icon);
            }
        } catch (error) {
            if (icon) icon.classList.remove('loading');
        }
    }

    async checkThumbnailReady(filename) {
        try {
            const response = await fetch(`/check-thumbnail/${encodeURIComponent(filename)}`);
            const data = await response.json();
            return data.ready;
        } catch (error) {
            return false;
        }
    }

    async pollThumbnail(filename, img, icon, attempts = 0) {
        if (attempts > 10) {
            if (icon) icon.classList.remove('loading');
            return;
        }

        setTimeout(async () => {
            const ready = await this.checkThumbnailReady(filename);
            if (ready) {
                this.showThumbnail(img, icon);
            } else {
                this.pollThumbnail(filename, img, icon, attempts + 1);
            }
        }, 1000 + (attempts * 500));
    }

    showThumbnail(img, icon) {
        img.onload = () => {
            img.classList.add('loaded');
            if (icon) {
                icon.classList.remove('loading');
                icon.classList.add('hidden');
            }
        };
        
        img.onerror = () => {
            if (icon) {
                icon.classList.remove('loading');
                icon.textContent = '❌';
            }
        };
        
        const src = img.dataset.src;
        img.src = src + (src.includes('?') ? '&' : '?') + 't=' + Date.now();
    }

    loadAllThumbnails() {
        document.querySelectorAll('.lazy-thumbnail').forEach(img => {
            this.loadThumbnail(img);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ThumbnailLoader();
});