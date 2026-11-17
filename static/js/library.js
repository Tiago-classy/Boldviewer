'use strict';
(() => {
    const library = document.querySelector('[data-library]');
    if (!library) return;
    const search = library.querySelector('[data-search]');
    const files = [...library.querySelectorAll('[data-file]')];
    const folders = [...library.querySelectorAll('[data-folder]')];
    const filters = [...library.querySelectorAll('[data-filter]')];
    let selected = 'all';
    let frame;
    const applyFilters = () => {
        const query = (search?.value || '').trim().toLocaleLowerCase();
        const matching = files.filter(file => file.dataset.name.includes(query));
        filters.forEach(button => {
            const type = button.dataset.filter;
            button.querySelector('strong').textContent = matching.filter(file => type === 'all' || file.dataset.kind === type).length;
        });
        let shown = 0;
        let shownFolders = 0;
        files.forEach(file => {
            file.hidden = !file.dataset.name.includes(query) || (selected !== 'all' && file.dataset.kind !== selected);
            if (!file.hidden) shown++;
        });
        folders.forEach(folder => {
            folder.hidden = selected !== 'all' || !folder.dataset.name.includes(query);
            if (!folder.hidden) shownFolders++;
        });
        const counter = library.querySelector('[data-result-count]');
        if (counter) counter.textContent = `${shown} ${shown === 1 ? 'file' : 'files'}`;
        const summary = library.querySelector('[data-summary]');
        if (summary) summary.textContent = `${shownFolders} ${shownFolders === 1 ? 'folder' : 'folders'} · ${shown} ${shown === 1 ? 'file' : 'files'}`;
        const folderCount = library.querySelector('[data-folder-count]');
        if (folderCount) folderCount.textContent = shownFolders;
        const folderSection = library.querySelector('.folder-section');
        if (folderSection) folderSection.hidden = !shownFolders;
        const mediaSection = library.querySelector('.media-section');
        if (mediaSection) mediaSection.hidden = !shown;
        const empty = library.querySelector('.search-empty');
        if (empty) empty.hidden = shown + shownFolders > 0 || !files.length && !folders.length;
        // Hidden cards must not start thumbnail work; re-observe those newly shown.
        library.dispatchEvent(new Event('library-filter'));
    };
    library.querySelector('.library-controls')?.removeAttribute('hidden');
    library.querySelector('.type-filters')?.removeAttribute('hidden');
    search?.addEventListener('input', () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(applyFilters);
    });
    filters.forEach(button => button.addEventListener('click', () => {
        selected = button.dataset.filter;
        filters.forEach(filter => filter.setAttribute('aria-pressed', String(filter === button)));
        applyFilters();
    }));
    library.querySelector('[data-clear]')?.addEventListener('click', () => {
        search.value = '';
        selected = 'all';
        filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === 'all')));
        applyFilters();
        search.focus();
    });
    const sort = library.querySelector('[data-sort]');
    const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
    sort?.addEventListener('change', () => {
        const byName = (a, b) => collator.compare(a.dataset.name, b.dataset.name);
        const ordered = [...files].sort((a, b) => {
            if (sort.value === 'newest') return Number(b.dataset.modified) - Number(a.dataset.modified) || byName(a, b);
            if (sort.value === 'largest') return Number(b.dataset.size) - Number(a.dataset.size) || byName(a, b);
            return sort.value === 'name-desc' ? byName(b, a) : byName(a, b);
        });
        const fragment = document.createDocumentFragment();
        ordered.forEach(file => fragment.append(file));
        library.querySelector('[data-files]')?.append(fragment);
    });
    const setView = view => {
        library.querySelector('[data-files]')?.classList.toggle('is-list', view === 'list');
        library.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === view)));
    };
    try { setView(localStorage.getItem('bold-view') || 'grid'); } catch { /* Storage can be disabled. */ }
    library.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
        setView(button.dataset.view);
        try { localStorage.setItem('bold-view', button.dataset.view); } catch { /* Keep the current view. */ }
    }));
})();
