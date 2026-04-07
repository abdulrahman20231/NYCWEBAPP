const state = {
    filters: {
        search: "",
        sources: [],
        boroughs: [],
        neighborhoods: [],
        min_price: "",
        max_price: "",
        min_beds: "",
        min_baths: "",
        pet_friendly: false,
        furnished: false,
        has_doorman: false,
        has_laundry: false,
        near_subway: false,
        allows_guarantors: false,
        featured_only: false,
        sort_by: "featured",
    },
    listings: [],
    filterOptions: null,
    saved: new Set(JSON.parse(localStorage.getItem("rentscout-saved") || "[]")),
};

const elements = {
    searchInput: document.querySelector("#searchInput"),
    sortSelect: document.querySelector("#sortSelect"),
    minPrice: document.querySelector("#minPrice"),
    maxPrice: document.querySelector("#maxPrice"),
    minBeds: document.querySelector("#minBeds"),
    minBaths: document.querySelector("#minBaths"),
    petFriendly: document.querySelector("#petFriendly"),
    furnished: document.querySelector("#furnished"),
    hasDoorman: document.querySelector("#hasDoorman"),
    hasLaundry: document.querySelector("#hasLaundry"),
    nearSubway: document.querySelector("#nearSubway"),
    allowsGuarantors: document.querySelector("#allowsGuarantors"),
    featuredOnly: document.querySelector("#featuredOnly"),
    sourceFilters: document.querySelector("#sourceFilters"),
    boroughFilters: document.querySelector("#boroughFilters"),
    neighborhoodFilters: document.querySelector("#neighborhoodFilters"),
    listingGrid: document.querySelector("#listingGrid"),
    activeFilters: document.querySelector("#activeFilters"),
    resultsTitle: document.querySelector("#resultsTitle"),
    heroCount: document.querySelector("#heroCount"),
    savedCount: document.querySelector("#savedCount"),
    datasetSource: document.querySelector("#datasetSource"),
    clearFilters: document.querySelector("#clearFilters"),
    filterPanel: document.querySelector("#filterPanel"),
    mobileFilterToggle: document.querySelector("#mobileFilterToggle"),
    closeMobileFilters: document.querySelector("#closeMobileFilters"),
};

let map;
let markersLayer;

function initMap() {
    map = L.map("map", {
        zoomControl: true,
        scrollWheelZoom: true,
    }).setView([40.738, -73.97], 11);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    markersLayer = L.layerGroup().addTo(map);
}

function persistSaved() {
    localStorage.setItem("rentscout-saved", JSON.stringify([...state.saved]));
    elements.savedCount.textContent = state.saved.size;
}

function debounce(callback, delay = 250) {
    let timeoutId;
    return (...args) => {
        window.clearTimeout(timeoutId);
        timeoutId = window.setTimeout(() => callback(...args), delay);
    };
}

function selectedValues(container) {
    return [...container.querySelectorAll("input:checked")].map((input) => input.value);
}

function renderCheckGroup(container, values, groupName) {
    container.innerHTML = values
        .map(
            (value) => `
            <label class="chip">
                <input type="checkbox" name="${groupName}" value="${value}">
                <span>${value}</span>
            </label>
        `
        )
        .join("");

    container.querySelectorAll("input").forEach((input) => {
        input.addEventListener("change", () => {
            state.filters[groupName] = selectedValues(container);
            fetchListings();
        });
    });
}

function paramsFromState() {
    const params = new URLSearchParams();
    const { filters } = state;

    if (filters.search) params.set("search", filters.search);
    if (filters.sources.length) params.set("source", filters.sources.join(","));
    if (filters.boroughs.length) params.set("borough", filters.boroughs.join(","));
    if (filters.neighborhoods.length) params.set("neighborhood", filters.neighborhoods.join(","));
    if (filters.min_price) params.set("min_price", filters.min_price);
    if (filters.max_price) params.set("max_price", filters.max_price);
    if (filters.min_beds) params.set("min_beds", filters.min_beds);
    if (filters.min_baths) params.set("min_baths", filters.min_baths);
    if (filters.pet_friendly) params.set("pet_friendly", "true");
    if (filters.furnished) params.set("furnished", "true");
    if (filters.has_doorman) params.set("has_doorman", "true");
    if (filters.has_laundry) params.set("has_laundry", "true");
    if (filters.near_subway) params.set("near_subway", "true");
    if (filters.allows_guarantors) params.set("allows_guarantors", "true");
    if (filters.featured_only) params.set("featured_only", "true");
    params.set("sort_by", filters.sort_by);
    return params;
}

function renderActiveFilters() {
    const labels = [];
    const { filters } = state;

    if (filters.search) labels.push(`Search: ${filters.search}`);
    filters.sources.forEach((value) => labels.push(value));
    filters.boroughs.forEach((value) => labels.push(value));
    filters.neighborhoods.forEach((value) => labels.push(value));
    if (filters.min_price) labels.push(`Min $${Number(filters.min_price).toLocaleString()}`);
    if (filters.max_price) labels.push(`Max $${Number(filters.max_price).toLocaleString()}`);
    if (filters.min_beds) labels.push(`${filters.min_beds}+ beds`);
    if (filters.min_baths) labels.push(`${filters.min_baths}+ baths`);
    if (filters.pet_friendly) labels.push("Pet friendly");
    if (filters.furnished) labels.push("Furnished");
    if (filters.has_doorman) labels.push("Doorman");
    if (filters.has_laundry) labels.push("Laundry");
    if (filters.near_subway) labels.push("Near subway");
    if (filters.allows_guarantors) labels.push("Guarantors ok");
    if (filters.featured_only) labels.push("Featured only");

    elements.activeFilters.innerHTML = labels.map((label) => `<span class="filter-pill">${label}</span>`).join("");
}

function tagsForListing(listing) {
    return [
        listing.pet_friendly ? "Pets" : "",
        listing.furnished ? "Furnished" : "",
        listing.has_doorman ? "Doorman" : "",
        listing.has_laundry ? "Laundry" : "",
        listing.near_subway ? "Subway" : "",
        listing.allows_guarantors ? "Guarantors ok" : "",
        listing.property_type,
    ].filter(Boolean);
}

function formatBeds(listing) {
    const title = (listing.title || "").toLowerCase();
    const description = (listing.description || "").toLowerCase();
    if (listing.beds > 0) {
        return `${listing.beds} bd`;
    }
    if (title.includes("studio") || description.includes("studio")) {
        return "Studio";
    }
    return "Beds on source";
}

function formatSqft(listing) {
    if (listing.sqft > 0) {
        return `${Number(listing.sqft).toLocaleString()} sq ft`;
    }
    return "Size on source";
}

function renderListings() {
    if (!state.listings.length) {
        elements.listingGrid.innerHTML = `
            <div class="empty-state">
                <h3>No rentals matched these filters.</h3>
                <p>Try widening your budget, removing a neighborhood, or turning off a few amenity constraints.</p>
            </div>
        `;
        return;
    }

    elements.listingGrid.innerHTML = state.listings
        .map((listing) => {
            const saved = state.saved.has(listing.id);
            const tags = tagsForListing(listing)
                .map((tag) => `<span class="listing-tag">${tag}</span>`)
                .join("");

            return `
                <article class="listing-card">
                    <div class="listing-image" style="background-image:url('${listing.image_url}')">
                        ${listing.featured ? '<span class="featured-badge">Featured</span>' : ""}
                        <button class="heart-button ${saved ? "is-saved" : ""}" type="button" data-save-id="${listing.id}" aria-label="Save listing">
                            ${saved ? "♥" : "♡"}
                        </button>
                    </div>
                    <div class="listing-body">
                        <div class="listing-price-row">
                            <div>
                                <div class="listing-price">$${Number(listing.price).toLocaleString()}<span>/mo</span></div>
                                <p class="listing-subtitle">${listing.neighborhood}, ${listing.borough}</p>
                            </div>
                            <div class="listing-meta">
                                <span>${formatBeds(listing)}</span>
                                <span>${listing.baths} ba</span>
                                <span>${formatSqft(listing)}</span>
                            </div>
                        </div>
                        <div>
                            <div class="listing-header">
                                <h3 class="listing-title">${listing.title}</h3>
                                <span class="source-badge">${listing.source_label}</span>
                            </div>
                            <p class="listing-description">${listing.description}</p>
                        </div>
                        <div class="listing-tags">${tags}</div>
                        <div class="listing-footer">
                            <span>${listing.address}</span>
                            <div class="detail-actions">
                                <a class="listing-link" href="/listings/${listing.id}">View details</a>
                                <a class="secondary-link" href="${listing.listing_url}" target="_blank" rel="noreferrer">Open source</a>
                            </div>
                        </div>
                    </div>
                </article>
            `;
        })
        .join("");

    elements.listingGrid.querySelectorAll("[data-save-id]").forEach((button) => {
        button.addEventListener("click", () => toggleSaved(button.dataset.saveId));
    });
}

function renderMap() {
    markersLayer.clearLayers();

    if (!state.listings.length) {
        map.setView([40.738, -73.97], 11);
        return;
    }

    const bounds = [];
    state.listings.forEach((listing) => {
        if (!listing.latitude || !listing.longitude) {
            return;
        }
        const marker = L.marker([listing.latitude, listing.longitude]).bindPopup(`
            <strong>${listing.title}</strong><br>
            ${listing.neighborhood}, ${listing.borough}<br>
            $${Number(listing.price).toLocaleString()}/mo<br>
            <a href="/listings/${listing.id}">View details</a>
        `);
        marker.addTo(markersLayer);
        bounds.push([listing.latitude, listing.longitude]);
    });

    if (bounds.length) {
        map.fitBounds(bounds, { padding: [40, 40] });
    }
}

async function fetchFilterOptions() {
    const response = await fetch("/api/filter-options");
    state.filterOptions = await response.json();
    renderCheckGroup(elements.sourceFilters, state.filterOptions.sources.map((source) => source.key), "sources");
    elements.sourceFilters.querySelectorAll("span").forEach((label, index) => {
        label.textContent = state.filterOptions.sources[index].label;
    });
    renderCheckGroup(elements.boroughFilters, state.filterOptions.boroughs, "boroughs");
    renderCheckGroup(elements.neighborhoodFilters, state.filterOptions.neighborhoods, "neighborhoods");
}

async function fetchListings() {
    renderActiveFilters();
    const response = await fetch(`/api/listings?${paramsFromState().toString()}`);
    const payload = await response.json();
    state.listings = payload.items;
    elements.resultsTitle.textContent = `${payload.count} rentals match`;
    elements.heroCount.textContent = `${payload.count} homes`;
    elements.datasetSource.innerHTML = `
        <span>Loaded from</span>
        <strong>${payload.source.kind === "aggregated" ? "multiple sources" : payload.source.kind === "single-source" ? "single source" : "seed sample data"}</strong>
        <span>(${payload.source.file})</span>
    `;
    renderListings();
    renderMap();
}

function toggleSaved(listingId) {
    if (state.saved.has(listingId)) {
        state.saved.delete(listingId);
    } else {
        state.saved.add(listingId);
    }
    persistSaved();
    renderListings();
}

function resetFilters() {
    state.filters = {
        search: "",
        sources: [],
        boroughs: [],
        neighborhoods: [],
        min_price: "",
        max_price: "",
        min_beds: "",
        min_baths: "",
        pet_friendly: false,
        furnished: false,
        has_doorman: false,
        has_laundry: false,
        near_subway: false,
        allows_guarantors: false,
        featured_only: false,
        sort_by: "featured",
    };

    elements.searchInput.value = "";
    elements.sortSelect.value = "featured";
    elements.minPrice.value = "";
    elements.maxPrice.value = "";
    elements.minBeds.value = "";
    elements.minBaths.value = "";
    [
        elements.petFriendly,
        elements.furnished,
        elements.hasDoorman,
        elements.hasLaundry,
        elements.nearSubway,
        elements.allowsGuarantors,
        elements.featuredOnly,
    ].forEach((checkbox) => {
        checkbox.checked = false;
    });
    document.querySelectorAll(".chip input").forEach((checkbox) => {
        checkbox.checked = false;
    });
    fetchListings();
}

function bindInputs() {
    const debouncedSearch = debounce((event) => {
        state.filters.search = event.target.value.trim();
        fetchListings();
    });

    elements.searchInput.addEventListener("input", debouncedSearch);

    elements.sortSelect.addEventListener("change", (event) => {
        state.filters.sort_by = event.target.value;
        fetchListings();
    });

    [
        [elements.minPrice, "min_price"],
        [elements.maxPrice, "max_price"],
        [elements.minBeds, "min_beds"],
        [elements.minBaths, "min_baths"],
    ].forEach(([input, key]) => {
        input.addEventListener(
            "input",
            debounce((event) => {
                state.filters[key] = event.target.value.trim();
                fetchListings();
            })
        );
    });

    [
        [elements.petFriendly, "pet_friendly"],
        [elements.furnished, "furnished"],
        [elements.hasDoorman, "has_doorman"],
        [elements.hasLaundry, "has_laundry"],
        [elements.nearSubway, "near_subway"],
        [elements.allowsGuarantors, "allows_guarantors"],
        [elements.featuredOnly, "featured_only"],
    ].forEach(([input, key]) => {
        input.addEventListener("change", (event) => {
            state.filters[key] = event.target.checked;
            fetchListings();
        });
    });

    elements.clearFilters.addEventListener("click", resetFilters);
    elements.mobileFilterToggle.addEventListener("click", () => {
        elements.filterPanel.classList.add("mobile-open");
    });
    elements.closeMobileFilters.addEventListener("click", () => {
        elements.filterPanel.classList.remove("mobile-open");
    });
}

async function boot() {
    initMap();
    persistSaved();
    bindInputs();
    await fetchFilterOptions();
    await fetchListings();
}

boot();
