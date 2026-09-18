let currentFeedId = null;
let articleWindow = null;
const articleLimit = document.querySelector("#news-article-limit");

async function loadFeed(feedId) {
    const reader = document.querySelector(".news-reader");

    if (!feedId || !reader) {
        return;
    }

    currentFeedId = feedId;

    reader.innerHTML =
        '<div class="news-empty">Loading news…</div>';

    let response;

    try {
        response = await fetch(
            `/news/feed/${feedId}?limit=${articleLimit.value}`
        );
    } catch (error) {
        reader.innerHTML =
            '<div class="news-empty">Could not load news.</div>';
        return;
    }

    if (!response.ok) {
        reader.innerHTML =
            '<div class="news-empty">Could not load news.</div>';
        return;
    }

    const items = await response.json();

    if (!items.length) {
        reader.innerHTML =
            '<div class="news-empty">No news items found.</div>';
        return;
    }

    reader.innerHTML = "";

    items.forEach(function (newsItem) {
        const article = document.createElement("article");
        article.className = "news-article";
        const title = document.createElement("h2");
        const link = document.createElement("a");

        link.href = newsItem.url;
        link.textContent = newsItem.title;

        link.addEventListener("click", function (event) {
            event.preventDefault();

            if (!articleWindow || articleWindow.closed) {
                articleWindow = window.open(
                    newsItem.url,
                    "alf-news-article"
                );
            } else {
                articleWindow.location.href = newsItem.url;
                articleWindow.focus();
            }
        });

        title.append(link);

        const metadata = document.createElement("div");
        metadata.className = "news-metadata";

        const published = new Date(newsItem.published_at);
        const date = String(published.getUTCDate()).padStart(2, "0");
        const month = String(
            published.getUTCMonth() + 1
        ).padStart(2, "0");
        const year = published.getUTCFullYear();
        const hours = String(
            published.getUTCHours()
        ).padStart(2, "0");
        const minutes = String(
            published.getUTCMinutes()
        ).padStart(2, "0");

        metadata.textContent =
            `${newsItem.feed_title} · ${date}-${month}-${year} ${hours}:${minutes}`;

        const summary = document.createElement("p");
        summary.textContent = newsItem.summary || "";

        article.append(title, metadata, summary);
        reader.append(article);
    });
}

document
    .querySelectorAll(".news-item")
    .forEach(function (item) {
        item.draggable = true;

        item.addEventListener("dragstart", function (event) {
            event.dataTransfer.setData(
                "text/plain",
                item.dataset.feedId
            );
        });

        item.addEventListener("click", function () {
            document
                .querySelectorAll(".news-item.active")
                .forEach(function (activeItem) {
                    activeItem.classList.remove("active");
                });

            item.classList.add("active");

            loadFeed(item.dataset.feedId);
        });
    });

if (articleLimit) {
    articleLimit.addEventListener("change", function () {
        if (currentFeedId) {
            loadFeed(currentFeedId);
        }
    });
}

document
    .querySelectorAll(".news-subject")
    .forEach(function (subject) {
        const subjectId = subject.dataset.subjectId;
        const storageKey = `news-subject-collapsed:${subjectId}`;

        if (localStorage.getItem(storageKey) === "true") {
            subject.classList.add("collapsed");
        }

        subject
            .querySelector(".news-subject-header h3")
            .addEventListener("click", function () {
                const collapsed =
                    subject.classList.toggle("collapsed");

                localStorage.setItem(
                    storageKey,
                    collapsed ? "true" : "false"
                );
            });

        subject.addEventListener("dragover", function (event) {
            if (event.dataTransfer.types.includes("text/plain")) {
                event.preventDefault();
                subject.classList.add("drag-over");
            }
        });

        subject.addEventListener("dragleave", function () {
            subject.classList.remove("drag-over");
        });

        subject.addEventListener("drop", async function (event) {
            event.preventDefault();
            subject.classList.remove("drag-over");

            const feedId = event.dataTransfer.getData("text/plain");

            if (!feedId) {
                return;
            }

            const subjectId = subject.dataset.subjectId;

            let response;

            try {
                response = await fetch(
                    `/news/feed/${feedId}/move`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({
                            subject_id: subjectId,
                        }),
                    }
                );
            } catch (error) {
                alfAlert("Move failed: network error.");
                return;
            }

            const result = await response.json();

            if (!response.ok) {
                alfAlert(
                    result.error || "The feed could not be moved."
                );
                return;
            }

            const feedItem = document.querySelector(
                `.news-item[data-feed-id="${feedId}"]`
            );

            if (!feedItem) {
                return;
            }

            subject
                .querySelector(".news-list")
                .append(feedItem);
        });
    });

document
    .querySelector("#news-delete-target")
    .addEventListener("dragover", function (event) {
        if (event.dataTransfer.types.includes("text/plain")) {
            event.preventDefault();
            this.classList.add("drag-over");
        }
    });

document
    .querySelector("#news-delete-target")
    .addEventListener("dragleave", function () {
        this.classList.remove("drag-over");
    });

document
    .querySelector("#news-delete-target")
    .addEventListener("drop", async function (event) {
        event.preventDefault();
        this.classList.remove("drag-over");

        const feedId = event.dataTransfer.getData("text/plain");

        if (!feedId) {
            return;
        }

        const feedItem = document.querySelector(
            `.news-item[data-feed-id="${feedId}"]`
        );

        if (!feedItem) {
            return;
        }

        const feedTitle = feedItem.textContent.trim();

        const confirmed = await alfConfirm(
            `Delete feed "${feedTitle}"?`
        );

        if (!confirmed) {
            return;
        }

        let response;

        try {
            response = await fetch(
                `/news/feed/${feedId}`,
                {
                    method: "DELETE",
                }
            );
        } catch (error) {
            alfAlert("Delete failed: network error.");
            return;
        }

        let result;

        try {
            result = await response.json();
        } catch (error) {
            alfAlert("Delete failed: invalid server response.");
            return;
        }

        if (!response.ok) {
            alfAlert(
                result.error || "The feed could not be deleted."
            );
            return;
        }

        if (currentFeedId === Number(feedId)) {
            currentFeedId = null;

            const reader = document.querySelector(".news-reader");

            if (reader) {
                reader.innerHTML =
                    '<div class="news-empty">Choose a feed to read its news.</div>';
            }
        }

        feedItem.remove();
    });

document
    .querySelector("#refresh-news")
    .addEventListener("click", async function () {
        const button = this;

        button.disabled = true;
        button.textContent = "Refreshing…";

        try {
            const response = await fetch(
                "/news/refresh",
                { method: "POST" }
            );

            if (!response.ok) {
                throw new Error("Refresh failed");
            }

            const result = await response.json();

            if (currentFeedId) {
                await loadFeed(currentFeedId);
            }

            button.textContent =
                `Refreshed (${result.imported} new)`;

        } catch (error) {
            button.textContent = "Refresh failed";
        }

        button.disabled = false;

        setTimeout(function () {
            button.textContent = "Refresh news";
        }, 2500);
    });

document
    .querySelector("#new-news-subject")
    .addEventListener("click", async function () {
        const name = await alfPrompt("Subject name:");

        if (!name || !name.trim()) {
            return;
        }

        const feedText = await alfPrompt(
            "Feed URL(s), separated by commas:"
        );

        if (!feedText || !feedText.trim()) {
            return;
        }

        const feedUrls = feedText
            .split(",")
            .map(function (url) {
                return url.trim();
            })
            .filter(function (url) {
                return url;
            });

        try {
            const response = await fetch(
                "/news/subject",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        name: name.trim(),
                        feed_urls: feedUrls,
                    }),
                }
            );

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    result.error || "Could not create subject."
                );
            }

            window.location.reload();

        } catch (error) {
            alfAlert(error.message);
        }
    });

document
    .querySelectorAll(".news-subject-menu")
    .forEach(function (button) {
        button.addEventListener("click", function (event) {
            event.stopPropagation();

            const subject = button.closest(".news-subject");

            if (!subject) {
                return;
            }

            document
                .querySelectorAll(".news-subject-actions")
                .forEach(function (menu) {
                    menu.remove();
                });

            const subjectId = subject.dataset.subjectId;
            const subjectName = subject.querySelector("h3").textContent.trim();

            const actions = document.createElement("div");
            actions.className = "news-subject-actions";
            const addFeed = document.createElement("button");
            addFeed.type = "button";
            addFeed.textContent = "Add feed";

            addFeed.addEventListener("click", async function () {
                const feedUrl = await alfPrompt(
                    "Feed URL:"
                );

                if (!feedUrl || !feedUrl.trim()) {
                    actions.remove();
                    return;
                }

                try {
                    const response = await fetch(
                        `/news/subject/${subjectId}/feed`,
                        {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({
                                feed_url: feedUrl.trim(),
                            }),
                        }
                    );

                    const result = await response.json();

                    if (!response.ok) {
                        throw new Error(
                            result.error || "Could not add feed."
                        );
                    }

                    window.location.reload();
                } catch (error) {
                    alfAlert(error.message);
                }
            });
            const rename = document.createElement("button");
            rename.type = "button";
            rename.textContent = "Rename";

            rename.addEventListener("click", async function () {
                const name = await alfPrompt(
                    "New subject name:",
                    subjectName
                );

                if (!name || !name.trim() || name.trim() === subjectName) {
                    actions.remove();
                    return;
                }

                try {
                    const response = await fetch(
                        `/news/subject/${subjectId}/rename`,
                        {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({
                                name: name.trim(),
                            }),
                        }
                    );

                    const result = await response.json();

                    if (!response.ok) {
                        throw new Error(
                            result.error || "Could not rename subject."
                        );
                    }

                    window.location.reload();
                } catch (error) {
                    alfAlert(error.message);
                }
            });

            const remove = document.createElement("button");
            remove.type = "button";
            remove.textContent = "Delete";

            remove.addEventListener("click", async function () {
                const confirmed = await alfConfirm(
                    `Delete subject "${subjectName}"?`
                );

                if (!confirmed) {
                    actions.remove();
                    return;
                }

                try {
                    const response = await fetch(
                        `/news/subject/${subjectId}`,
                        {
                            method: "DELETE",
                        }
                    );

                    const result = await response.json();

                    if (!response.ok) {
                        throw new Error(
                            result.error || "Could not delete subject."
                        );
                    }

                    window.location.reload();
                } catch (error) {
                    alfAlert(error.message);
                }
            });

            actions.append(addFeed, rename, remove);
            subject
                .querySelector(".news-subject-header")
                .after(actions);
        });
    });

document.addEventListener("click", function () {
    document
        .querySelectorAll(".news-subject-actions")
        .forEach(function (menu) {
            menu.remove();
        });
});
