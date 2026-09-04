// Trip prose lives in data/trip-text.json so index.html stays identical for
// every trip. Loaded before map.js and gallery.js; gallery.js reads the day
// titles and blurbs back off window.tripText once this resolves.
const tripText = fetch('data/trip-text.json')
    .then(response => (response.ok ? response.json() : {}))
    .catch(() => ({}));

window.tripText = tripText;
window.joinText = joinText;

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// [label](url) becomes a link; everything else is escaped, so a stray < or &
// in the prose cannot break the page.
function renderText(raw) {
    return escapeHtml(raw).replace(
        /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
        (match, label, url) =>
            `<a href="${url}" target="_blank" rel="noopener">${label}</a>`
    );
}

// A value may be given as an array purely to wrap long prose across several
// source lines. The entries are concatenated with nothing between them, so
// spacing is explicit: ["a ", "b"] is "a b", ["a", "b"] is "ab". Paragraphs
// still come from blank lines, whichever form is used.
function joinText(value) {
    return Array.isArray(value) ? value.join('') : (value || '');
}

// Blank lines separate paragraphs.
function paragraphs(raw) {
    return raw
        .split(/\n\s*\n/)
        .map(block => block.trim())
        .filter(Boolean)
        .map(block => `<p>${renderText(block)}</p>`)
        .join('');
}

function fill(selector, value) {
    const element = document.querySelector(selector);
    if (!element) {
        return;
    }
    const raw = joinText(value);
    // An empty or missing value leaves the section out entirely.
    if (!raw.trim()) {
        element.remove();
        return;
    }
    element.innerHTML = element.tagName === 'P'
        ? renderText(raw.trim())
        : paragraphs(raw);
}

tripText.then(text => {
    fill('.intro', text.intro);
    fill('.notes', text.notes);
});
