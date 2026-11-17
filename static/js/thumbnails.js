'use strict';
/** One queue, four requests at most. Checking a thumbnail also starts its generation. */
class ThumbnailLoader {
    constructor() {
        this.queue = [];
        this.active = 0;
        this.stopped = false;
        this.controller = new AbortController();
        this.images = [...document.querySelectorAll('.lazy-thumbnail')];
        this.observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !entry.target.closest('[hidden]')) this.enqueue(entry.target);
            });
        }, { rootMargin: '120px' }) : null;
        this.images.forEach(img => this.observer ? this.observer.observe(img) : this.enqueue(img));
        this.retryButton = document.querySelector('[data-retry-previews]');
        this.retryButton?.addEventListener('click', () => this.retryFailed());
        document.querySelector('[data-library]')?.addEventListener('library-filter', () => {
            this.updateRetryButton();
            this.images.forEach(img => {
                if (!img.dataset.queued && !img.closest('[hidden]')) {
                    if (this.observer) { this.observer.unobserve(img); this.observer.observe(img); }
                    else this.enqueue(img);
                }
            });
        });
        window.addEventListener('pagehide', () => {
            this.stopped = true;
            this.queue = [];
            this.controller.abort();
            this.observer?.disconnect();
        });
        window.addEventListener('pageshow', event => {
            if (event.persisted) {
                this.stopped = false;
                this.controller = new AbortController();
                this.images.filter(img => !img.classList.contains('loaded')).forEach(img => {
                    delete img.dataset.queued;
                    this.observer ? this.observer.observe(img) : this.enqueue(img);
                });
            }
        });
    }
    enqueue(img) {
        if (img.dataset.queued || this.stopped) return;
        delete img.dataset.failed;
        this.updateRetryButton();
        img.dataset.queued = 'true';
        img.parentElement.setAttribute('aria-busy', 'true');
        img.parentElement.querySelector('.file-fallback span').textContent = 'Preparing preview';
        this.observer?.unobserve(img);
        this.queue.push(img);
        this.drain();
    }
    drain() {
        while (!this.stopped && this.active < 4 && this.queue.length) {
            const img = this.queue.shift();
            if (img.closest('[hidden]')) { delete img.dataset.queued; continue; }
            this.active++;
            this.load(img).finally(() => { this.active--; this.drain(); });
        }
    }
    async load(img) {
        const signal = this.controller.signal;
        try {
            for (let attempt = 0; attempt < 12 && !signal.aborted; attempt++) {
                if (img.closest('[hidden]')) { delete img.dataset.queued; return; }
                if (document.hidden) {
                    await this.waitUntilVisible(signal);
                    attempt--;
                    continue;
                }
                const statusUrl = new URL(img.dataset.statusUrl, location.href);
                if (img.dataset.retry) { statusUrl.searchParams.set('retry', '1'); delete img.dataset.retry; }
                const response = await fetch(statusUrl, {
                    signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]),
                    headers: { Accept: 'application/json' }, cache: 'no-store',
                });
                if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) break;
                const data = await response.json();
                if (data.ready && data.url) {
                    await new Promise((resolve, reject) => {
                        const cleanup = () => { clearTimeout(timer); signal.removeEventListener('abort', abort); img.onload = img.onerror = null; };
                        const abort = () => { cleanup(); reject(signal.reason); };
                        const timer = setTimeout(() => { cleanup(); reject(new Error('Image load timed out')); }, 15000);
                        signal.addEventListener('abort', abort, { once: true });
                        img.onload = () => { cleanup(); img.classList.add('loaded'); img.parentElement.removeAttribute('aria-busy'); img.parentElement.querySelector('.file-fallback').hidden = true; resolve(); };
                        img.onerror = () => { cleanup(); reject(new Error('Image could not load')); };
                        // Stable URL allows private browser caching and conditional requests.
                        img.src = data.url;
                    });
                    return;
                }
                if (['failed', 'unsupported'].includes(data.state)) break;
                await this.delay(Math.min(800 * 1.5 ** attempt, 5000), signal);
            }
            if (!signal.aborted) this.unavailable(img);
        } catch {
            if (!signal.aborted) this.unavailable(img);
        }
    }
    unavailable(img) {
        img.parentElement.removeAttribute('aria-busy');
        const label = img.parentElement.querySelector('.file-fallback span');
        if (label) label.textContent = 'Preview unavailable';
        img.dataset.failed = 'true';
        this.updateRetryButton();
    }
    updateRetryButton() {
        if (this.retryButton) this.retryButton.hidden = !this.images.some(img => img.dataset.failed && !img.closest('[hidden]'));
    }
    retryFailed() {
        this.images.filter(img => img.dataset.failed && !img.closest('[hidden]')).forEach(img => {
            delete img.dataset.failed;
            delete img.dataset.queued;
            img.dataset.retry = 'true';
            img.parentElement.querySelector('.file-fallback span').textContent = 'Preparing preview';
            this.enqueue(img);
        });
        this.updateRetryButton();
    }
    waitUntilVisible(signal) {
        return new Promise((resolve, reject) => {
            const cleanup = () => { document.removeEventListener('visibilitychange', visible); signal.removeEventListener('abort', abort); };
            const visible = () => { if (!document.hidden) { cleanup(); resolve(); } };
            const abort = () => { cleanup(); reject(signal.reason); };
            if (signal.aborted) { reject(signal.reason); return; }
            document.addEventListener('visibilitychange', visible);
            signal.addEventListener('abort', abort, { once: true });
            visible();
        });
    }
    delay(ms, signal) {
        return new Promise((resolve, reject) => {
            if (signal.aborted) { reject(signal.reason); return; }
            const abort = () => { clearTimeout(timer); reject(signal.reason); };
            const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
            signal.addEventListener('abort', abort, { once: true });
        });
    }
}
new ThumbnailLoader();
