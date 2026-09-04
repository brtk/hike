// Photos come from data/photos.json rather than a folder listing: browsers
// cannot enumerate a directory over HTTP. Regenerate the file after adding
// photos with:  python3 pytools/photo_exif.py trips/<trip>/photos
const gallery = document.getElementById('gallery');

// Fetch that resolves to a fallback instead of failing, for optional files.
function fetchJson(url, fallback) {
    return fetch(url)
        .then(response => (response.ok ? response.json() : fallback))
        .catch(() => fallback);
}

function caption(photo) {
    const parts = [];
    if (photo.timestamp) {
        parts.push(new Date(photo.timestamp).toLocaleString());
    }
    if (photo.alt !== null && photo.alt !== undefined) {
        parts.push(`${Math.round(photo.alt)} m`);
    }
    return parts.join(' &middot; ');
}

// Undated photos sort last, keeping their order from the file.
function byTimestamp(a, b) {
    if (!a.timestamp) {
        return b.timestamp ? 1 : 0;
    }
    if (!b.timestamp) {
        return -1;
    }
    return a.timestamp.localeCompare(b.timestamp);
}

function figureFor(photo, captions) {
    const figure = document.createElement('figure');
    figure.className = 'photo';

    const img = document.createElement('img');
    img.src = `photos/${photo.file}`;
    img.alt = photo.file;
    img.loading = 'lazy';
    figure.appendChild(img);

    // Only photos given a caption by hand get one; the stub leaves them empty.
    const written = captions[photo.file];
    if (written) {
        const note = document.createElement('figcaption');
        note.className = 'photo-caption';
        note.textContent = written;
        figure.appendChild(note);
    }

    const text = caption(photo);
    if (text) {
        const figcaption = document.createElement('figcaption');
        figcaption.innerHTML = text;
        figure.appendChild(figcaption);
    }

    return figure;
}

Promise.all([
    fetch('data/photos.json').then(response => {
        if (!response.ok) {
            throw new Error(`photos.json: ${response.status}`);
        }
        return response.json();
    }),
    // Captions are optional: the gallery works without the file.
    fetchJson('data/captions.json', {}),
    // Set by js/text.js, which loads first; {} if that file is missing.
    window.tripText || Promise.resolve({})
])
    .then(([photos, captions, text]) => {
        const dayText = text.days || {};
        if (photos.length === 0) {
            gallery.textContent = 'No photos yet.';
            return;
        }
        // Chronological within each day, days in order.
        const ordered = photos.slice().sort(
            (a, b) => (a.day - b.day) || byTimestamp(a, b)
        );

        const fragment = document.createDocumentFragment();
        let shownDay = null;
        ordered.forEach(photo => {
            if (photo.day !== shownDay) {
                const info = dayText[photo.day] || {};
                const heading = document.createElement('h3');
                heading.className = 'day-heading';
                const title = joinText(info.title).trim();
                heading.textContent = title
                    ? `Day ${photo.day} \u2014 ${title}`
                    : `Day ${photo.day}`;
                fragment.appendChild(heading);

                const blurb = joinText(info.blurb);
                if (blurb.trim()) {
                    const paragraph = document.createElement('p');
                    paragraph.className = 'day-blurb';
                    paragraph.innerHTML = renderText(blurb);
                    fragment.appendChild(paragraph);
                }
                shownDay = photo.day;
            }
            fragment.appendChild(figureFor(photo, captions));
        });
        gallery.appendChild(fragment);
    })
    .catch(error => {
        console.error('Could not load photos:', error);
        gallery.textContent = 'Could not load photos.';
    });
