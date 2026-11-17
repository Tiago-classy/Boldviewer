'use strict';
const menu = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#navigation');
function setMenu(open) {
    navigation?.classList.toggle('is-open', open);
    menu?.setAttribute('aria-expanded', String(open));
    menu?.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    document.querySelector('#main')?.toggleAttribute('inert', open);
    document.querySelector('.workspace-footer')?.toggleAttribute('inert', open);
}
menu?.addEventListener('click', () => {
    const open = !navigation.classList.contains('is-open');
    setMenu(open);
    if (open) navigation.querySelector('.side-nav a')?.focus();
});
document.addEventListener('keydown', event => {
    if (!navigation?.classList.contains('is-open')) return;
    if (event.key === 'Escape') {
        setMenu(false);
        menu.focus();
    }
    if (event.key === 'Tab') {
        const stops = [menu, ...navigation.querySelectorAll('a[href]')].filter(el => el.getClientRects().length);
        const index = stops.indexOf(document.activeElement);
        event.preventDefault();
        stops[(index + (event.shiftKey ? -1 : 1) + stops.length) % stops.length].focus();
    }
});
matchMedia('(min-width: 1101px)').addEventListener('change', event => { if (event.matches) setMenu(false); });
const preview = document.querySelector('[data-preview]');
if (preview) {
    const workspace = document.querySelector('[data-preview-workspace]');
    const region = workspace.querySelector('.file-preview');
    const toolbar = workspace.querySelector('.preview-toolbar');
    const details = workspace.querySelector('[data-media-details]');
    const modes = [...workspace.querySelectorAll('[data-image-mode]')];
    const fullscreen = workspace.querySelector('[data-fullscreen]');
    toolbar.hidden = false;
    const showError = () => {
        preview.hidden = true;
        region.classList.remove('is-actual');
        workspace.querySelector('.preview-error').hidden = false;
        modes.forEach(button => { button.disabled = true; });
        details.textContent = '';
    };
    const imageReady = () => {
        details.textContent = `${preview.naturalWidth.toLocaleString()} × ${preview.naturalHeight.toLocaleString()} px`;
        modes.forEach(button => { button.disabled = false; });
    };
    modes.forEach(button => button.addEventListener('click', () => {
        region.classList.toggle('is-actual', button.dataset.imageMode === 'actual');
        modes.forEach(mode => mode.setAttribute('aria-pressed', String(mode === button)));
        region.scrollTo(0, 0);
    }));
    if (document.fullscreenEnabled && workspace.requestFullscreen) {
        fullscreen.hidden = false;
        fullscreen.addEventListener('click', async () => {
            try {
                if (document.fullscreenElement) await document.exitFullscreen();
                else await workspace.requestFullscreen();
            } catch {
                const notice = document.querySelector('[data-preview-notice]');
                notice.hidden = false;
                notice.textContent = 'Fullscreen is unavailable in this browser window.';
            }
        });
        document.addEventListener('fullscreenchange', () => {
            fullscreen.textContent = document.fullscreenElement ? 'Exit fullscreen' : 'Fullscreen';
        });
    }
    preview.addEventListener('error', showError);
    preview.querySelector('source')?.addEventListener('error', showError);
    if (preview.tagName === 'IMG') {
        preview.addEventListener('load', imageReady);
        if (preview.complete) preview.naturalWidth ? imageReady() : showError();
    } else {
        const videoReady = () => {
            const duration = Number.isFinite(preview.duration) ? Math.floor(preview.duration) : null;
            const length = duration === null ? '' : `${Math.floor(duration / 60)}:${String(duration % 60).padStart(2, '0')} · `; // taste-skill-ignore: MM:SS video duration, not index numbering.
            details.textContent = `${length}${preview.videoWidth.toLocaleString()} × ${preview.videoHeight.toLocaleString()} px`;
        };
        preview.addEventListener('loadedmetadata', videoReady);
        if (preview.readyState >= 1) videoReady();
    }
}
