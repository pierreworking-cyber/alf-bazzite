document.addEventListener("DOMContentLoaded", () => {
    const readErrorMessage = async (response) => {
        try {
            const data = await response.json();
            return data.error || "Operation failed";
        } catch {
            return "Operation failed";
        }
    };

    const closeMenus = () => {
        document
            .querySelectorAll(".memory-category-actions")
            .forEach((menu) => menu.remove());
    };

    const createCategory = async (parentId = null) => {
        const prompt = parentId === null
            ? "New category:"
            : "New child category:";

        const name = await alfPrompt(prompt);

        if (!name || !name.trim()) {
            return;
        }

        const response = await fetch("/memory-categories", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                name: name.trim(),
                parent_id: parentId,
            }),
        });

        if (!response.ok) {
            await alfAlert(await readErrorMessage(response));
            return;
        }

        window.location.reload();
    };

    document
        .getElementById("new-memory-category")
        ?.addEventListener("click", () => createCategory());

    let draggedMemoryId = null;
    let memoryWasDragged = false;

    document
        .querySelectorAll(".memory[data-memory-id]")
        .forEach((memory) => {
            memory.addEventListener("dragstart", (event) => {
                draggedMemoryId = memory.dataset.memoryId;
                memoryWasDragged = true;
                event.dataTransfer.effectAllowed = "move";
            });

            memory.addEventListener("dragend", () => {
                draggedMemoryId = null;

                document
                    .querySelectorAll(".memory-taxonomy-header")
                    .forEach((header) => {
                        header.classList.remove(
                            "memory-category-drag-over"
                        );
                    });
            });

            memory.addEventListener("click", (event) => {
                if (memoryWasDragged) {
                    memoryWasDragged = false;
                    return;
                }

                if (event.target.closest("button")) {
                    return;
                }

                const link = memory.querySelector(".memory-select");

                if (link) {
                    window.location.href = link.href;
                }
            });
        });

    document
        .querySelectorAll(".memory-taxonomy-header")
        .forEach((header) => {
            header.addEventListener("dragover", (event) => {
                if (!draggedMemoryId) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                document
                    .querySelectorAll(".memory-category-drag-over")
                    .forEach((target) => {
                        if (target !== header) {
                            target.classList.remove(
                                "memory-category-drag-over"
                            );
                        }
                    });

                event.dataTransfer.dropEffect = "move";
                header.classList.add("memory-category-drag-over");
            });

            header.addEventListener("dragleave", () => {
                header.classList.remove(
                    "memory-category-drag-over"
                );
            });

            header.addEventListener("drop", async (event) => {
                event.preventDefault();
                event.stopPropagation();

                header.classList.remove(
                    "memory-category-drag-over"
                );

                if (!draggedMemoryId) {
                    return;
                }

                const category = header.closest(
                    ".memory-taxonomy-category"
                );
                const categoryId = category.dataset.categoryId;

                const response = await fetch(
                    `/memories/${draggedMemoryId}/category`,
                    {
                        method: "PATCH",
                        headers: {
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({
                            category_id: categoryId,
                        }),
                    }
                );

                draggedMemoryId = null;

                if (!response.ok) {
                    await alfAlert(await readErrorMessage(response));
                    return;
                }

                window.location.reload();
            });
        });

    document
        .querySelectorAll(".memory-taxonomy-category")
        .forEach((category) => {
            const collapseButton = category.querySelector(
                ":scope > .memory-taxonomy-header > .memory-category-collapse"
            );
            const children = category.querySelector(
                ":scope > ul"
            );

            if (!collapseButton || !children) {
                return;
            }

            const categoryId = category.dataset.categoryId;
            const storageKey =
                `memory-category-collapsed:${categoryId}`;

            if (localStorage.getItem(storageKey) === "true") {
                category.classList.add("collapsed");
                collapseButton.textContent = "▸";
                collapseButton.setAttribute(
                    "aria-label",
                    "Expand category"
                );
            }

            collapseButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                const collapsed =
                    category.classList.toggle("collapsed");

                collapseButton.textContent =
                    collapsed ? "▸" : "▾";

                collapseButton.setAttribute(
                    "aria-label",
                    collapsed
                        ? "Expand category"
                        : "Collapse category"
                );

                localStorage.setItem(
                    storageKey,
                    collapsed ? "true" : "false"
                );
            });
        });

    document
        .querySelectorAll(".memory-category-menu")
        .forEach((button) => {
            button.addEventListener("click", (event) => {
                event.stopPropagation();

                closeMenus();

                const category = button.closest(
                    ".memory-taxonomy-category"
                );

                const categoryId = category.dataset.categoryId;
                const categoryName = category.querySelector(
                    ".memory-taxonomy-header a"
                ).textContent.trim();

                const actions = document.createElement("div");
                actions.className = "memory-category-actions";

                const addChild = document.createElement("button");
                addChild.type = "button";
                addChild.textContent = "Add child";

                const rename = document.createElement("button");
                rename.type = "button";
                rename.textContent = "Rename";

                const remove = document.createElement("button");
                remove.type = "button";
                remove.textContent = "Delete";

                actions.append(
                    addChild,
                    rename,
                    remove
                );

                category.appendChild(actions);

                addChild.addEventListener("click", async () => {
                    await createCategory(Number(categoryId));
                });

                rename.addEventListener("click", async () => {
                    const name = await alfPrompt(
                        "Rename category:",
                        categoryName
                    );

                    if (!name || !name.trim()) {
                        return;
                    }

                    const response = await fetch(
                        `/memory-categories/${categoryId}`,
                        {
                            method: "PATCH",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({
                                name: name.trim(),
                            }),
                        }
                    );

                    if (!response.ok) {
                        await alfAlert(
                            await readErrorMessage(response)
                        );
                        return;
                    }

                    window.location.reload();
                });

                remove.addEventListener("click", async () => {
                    const confirmed = await alfConfirm(
                        `Delete "${categoryName}"?`
                    );

                    if (!confirmed) {
                        return;
                    }

                    const response = await fetch(
                        `/memory-categories/${categoryId}`,
                        {
                            method: "DELETE",
                        }
                    );

                    if (!response.ok) {
                        await alfAlert(
                            await readErrorMessage(response)
                        );
                        return;
                    }

                    window.location.reload();
                });
            });
        });

    document.addEventListener("click", closeMenus);
});

document.querySelectorAll(".memory").forEach((memory) => {
    const expandButton = memory.querySelector(".memory-expand");
    const rollupButton = memory.querySelector(".memory-rollup");
    const preview = memory.querySelector(".memory-preview");
    const full = memory.querySelector(".memory-full");

    if (!expandButton || !rollupButton || !preview || !full) {
        return;
    }

    expandButton.addEventListener("click", () => {
        preview.hidden = true;
        full.hidden = false;
        expandButton.hidden = true;
        rollupButton.hidden = false;
    });

    rollupButton.addEventListener("click", () => {
        full.hidden = true;
        preview.hidden = false;
        rollupButton.hidden = true;
        expandButton.hidden = false;
    });
});
