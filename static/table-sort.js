/* כלי מיון עמודות גנרי - משותף לכל הטבלאות במערכת.
 * שימוש:
 *   const sortState = createSortState();
 *   attachSortableHeaders(theadEl, sortState, () => render());
 *   const sortedRows = sortRows(rows, sortState);
 */
function createSortState(defaultKey, defaultType, defaultDir) {
    return { key: defaultKey || null, type: defaultType || 'text', dir: defaultDir || 1 };
}

function sortRows(rows, state) {
    if (!state || !state.key) return rows;
    const { key, type, dir } = state;
    return [...rows].sort((a, b) => {
        let av = a[key], bv = b[key];
        if (type === 'number') {
            av = Number(av) || 0; bv = Number(bv) || 0;
            return (av - bv) * dir;
        }
        if (type === 'date') {
            av = av ? new Date(av).getTime() : 0;
            bv = bv ? new Date(bv).getTime() : 0;
            return (av - bv) * dir;
        }
        av = String(av ?? '').trim();
        bv = String(bv ?? '').trim();
        return av.localeCompare(bv, 'he') * dir;
    });
}

function attachSortableHeaders(theadEl, state, onSort) {
    if (!theadEl) return;
    theadEl.querySelectorAll('[data-sort-key]').forEach(th => {
        th.classList.add('sp-sortable');
        if (!th.querySelector('.sp-sort-icon')) {
            const icon = document.createElement('i');
            icon.className = 'fa-solid fa-sort sp-sort-icon';
            th.appendChild(icon);
        }
        th.addEventListener('click', () => {
            const key = th.dataset.sortKey;
            const type = th.dataset.sortType || 'text';
            if (state.key === key) {
                state.dir *= -1;
            } else {
                state.key = key;
                state.type = type;
                state.dir = 1;
            }
            theadEl.querySelectorAll('.sp-sort-icon').forEach(i => { i.className = 'fa-solid fa-sort sp-sort-icon'; });
            const activeIcon = th.querySelector('.sp-sort-icon');
            activeIcon.className = `fa-solid ${state.dir === 1 ? 'fa-sort-up' : 'fa-sort-down'} sp-sort-icon active`;
            onSort();
        });
    });
}
