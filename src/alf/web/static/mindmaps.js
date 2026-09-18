let currentMindmapId = null;
let currentMindmapCategory = "Uncategorised";

function showNotification(message, isError = false) {
    const notification = document.querySelector("#save-notification");

    if (!notification) {
        return;
    }

    clearTimeout(showNotification.timeout);

    notification.textContent = message;
    notification.classList.toggle("error", isError);

    notification.classList.remove("show");
    void notification.offsetWidth;
    notification.classList.add("show");

    if (!isError) {
        showNotification.timeout = setTimeout(function () {
            notification.classList.remove("show");
        }, 3000);
    }
}

async function readErrorMessage(response, fallback) {
    try {
        const data = await response.json();

        if (data && typeof data.error === "string" && data.error) {
            return data.error;
        }
    } catch (error) {
    }

    return fallback;
}

const options = {
    container: "jsmind-container",
    editable: true,
    theme: "primary",
    mode: "full",
    view: {
        draggable: true,
        hide_scrollbars_when_draggable: true
    }
};

const mindmap = new jsMind(options);

const mindmapContainer = document.getElementById("jsmind-container");

let touchStartX = 0;
let touchStartY = 0;
let draggingCanvas = false;

mindmapContainer.addEventListener("touchstart", (event) => {
    if (event.touches.length !== 1) {
        draggingCanvas = false;
        return;
    }

    const target = event.target;

    // Don't canvas-drag when touching a node or expander.
    if (target.closest("jmnode, jmexpander")) {
        draggingCanvas = false;
        return;
    }

    draggingCanvas = true;
    touchStartX = event.touches[0].clientX;
    touchStartY = event.touches[0].clientY;
}, { passive: true });

mindmapContainer.addEventListener("touchmove", (event) => {
    if (!draggingCanvas || event.touches.length !== 1) {
        return;
    }

    const touch = event.touches[0];
    const dx = touchStartX - touch.clientX;
    const dy = touchStartY - touch.clientY;

    mindmapContainer.querySelector(".jsmind-inner").scrollBy(dx, dy);

    touchStartX = touch.clientX;
    touchStartY = touch.clientY;

    event.preventDefault();
}, { passive: false });

mindmapContainer.addEventListener("touchend", () => {
    draggingCanvas = false;
}, { passive: true });

mindmapContainer.addEventListener("touchcancel", () => {
    draggingCanvas = false;
}, { passive: true });

document
    .querySelector("#add-child-node")
    .addEventListener("click", function () {
        const selectedNode = mindmap.get_selected_node();

        if (!selectedNode) {
            return;
        }

        const nodeId = jsMind.util.uuid.newid();

        mindmap.add_node(
            selectedNode,
            nodeId,
            "New Node"
        );

        mindmap.select_node(nodeId);
        mindmap.begin_edit(nodeId);
    });

document
    .querySelector("#add-sibling-node")
    .addEventListener("click", function () {
        const selectedNode = mindmap.get_selected_node();

        if (!selectedNode || selectedNode.isroot) {
            return;
        }

        const nodeId = jsMind.util.uuid.newid();

        mindmap.insert_node_after(
            selectedNode,
            nodeId,
            "New Node"
        );

        mindmap.select_node(nodeId);
        mindmap.begin_edit(nodeId);
    });

document
    .querySelector("#edit-node")
    .addEventListener("click", function () {
        const selectedNode = mindmap.get_selected_node();

        if (!selectedNode) {
            return;
        }

        mindmap.begin_edit(selectedNode);
    });

document
    .querySelector("#delete-node")
    .addEventListener("click", function () {
        const selectedNode = mindmap.get_selected_node();

        if (!selectedNode || selectedNode.isroot) {
            return;
        }

        const parentNode = selectedNode.parent;

        mindmap.select_node(parentNode);
        mindmap.remove_node(selectedNode);
    });

document
    .querySelector("#new-mindmap")
    .addEventListener("click", function () {
        currentMindmapId = null;
        currentMindmapCategory = "Uncategorised";

        document.querySelector("#mindmap-empty").style.display =
            "none";

        const mindmapName = "New Mindmap";

        const newMind = {
            meta: {
                name: mindmapName,
                author: "ALF",
                version: "0.1"
            },
            format: "node_array",
            data: [
                {
                    id: "root",
                    isroot: true,
                    topic: mindmapName,
                    expanded: true
                }
            ]
        };

        mindmap.show(newMind);
        mindmap.select_node("root");
        mindmap.view.e_panel.focus();
    });

document
    .querySelector("#new-mindmap-category")
    .addEventListener("click", async function () {
        const name = await alfPrompt("New category:");

        if (name === null) {
            return;
        }

        const trimmedName = name.trim();

        if (!trimmedName) {
            return;
        }

        let response;

        try {
            response = await fetch(
                "/mindmap-categories",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        name: trimmedName
                    })
                }
            );
        } catch (error) {
            showNotification("Create failed: network error.", true);
            return;
        }

        if (!response.ok) {
            const serverError = await readErrorMessage(
                response,
                "The category could not be created."
            );

            showNotification(
                `Create failed: ${serverError}`,
                true
            );
            return;
        }

        window.location.reload();
    });

document
    .querySelector("#save-mindmap")
    .addEventListener("click", async function () {
        const documentData = mindmap.get_data("node_array");

        const rootNode = documentData.data.find(
            function (node) {
                return node.isroot;
            }
        );

        const name = rootNode
            ? rootNode.topic.trim() || "New Mindmap"
            : "New Mindmap";

        const isNewMindmap = currentMindmapId === null;

        let response;

        try {
            response = await fetch("/mindmaps/save", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    id: currentMindmapId,
                    category: currentMindmapCategory,
                    name: name,
                    content: JSON.stringify(documentData)
                })
            });
        } catch (error) {
            showNotification("Save failed: network error.", true);
            return;
        }

        if (!response.ok) {
            const serverError = await readErrorMessage(
                response,
                "The map could not be saved."
            );

            showNotification(`Save failed: ${serverError}`, true);
            return;
        }

        const result = await response.json();

        currentMindmapId = result.id;

        showNotification("Map saved");

        if (isNewMindmap) {
            const mapItem = document.createElement("button");
            mapItem.type = "button";
            mapItem.className = "mindmap-item";
            mapItem.dataset.mindmapId = result.id;

            mapItem.draggable = true;

            mapItem.addEventListener("dragstart", function (event) {
                event.dataTransfer.setData(
                    "text/plain",
                    mapItem.dataset.mindmapId
                );
            });

            bindMindmapItemClick(mapItem);

            const mapName = document.createElement("span");
            mapName.textContent = name;

            mapItem.append(mapName);

            const uncategorisedCategory =
                Array.from(
                    document.querySelectorAll(".mindmap-category")
                ).find(
                    function (category) {
                        return (
                            category.querySelector("h3")?.textContent.trim() ===
                            "Uncategorised"
                        );
                    }
                );

            if (uncategorisedCategory) {
                uncategorisedCategory
                    .querySelector(".mindmap-list")
                    .append(mapItem);
            }
        }
    });

    document
        .querySelectorAll(".mindmap-item")
        .forEach(function (item) {
            item.draggable = true;

            item.addEventListener("dragstart", function (event) {
                event.dataTransfer.setData(
                    "text/plain",
                    item.dataset.mindmapId
                );
            });
        });

    document
        .querySelectorAll(".mindmap-category")
        .forEach(function (category) {
            const heading = category.querySelector("h3");

                if (
                    heading.textContent.trim() !==
                    "Uncategorised"
                ) {
                    heading.draggable = true;
                }

            heading.addEventListener("dragstart", function (event) {
                event.dataTransfer.setData(
                    "application/x-mindmap-category",
                    category.dataset.categoryId
                );
            });
        });

    document
        .querySelectorAll(".mindmap-category")
        .forEach(function (category) {
                category.addEventListener("dragover", function (event) {
                    if (
                        event.dataTransfer.types.includes(
                            "application/x-mindmap-category"
                        ) ||
                        event.dataTransfer.types.includes("text/plain")
                    ) {
                        event.preventDefault();
                    }
                });

            category.addEventListener("drop", async function (event) {
                event.preventDefault();

                const categoryId =
                    event.dataTransfer.getData(
                        "application/x-mindmap-category"
                    );

                if (categoryId) {
                    const draggedCategory =
                        document.querySelector(
                            `.mindmap-category[data-category-id="${categoryId}"]`
                        );

                    if (!draggedCategory || draggedCategory === category) {
                        return;
                    }

                    const categories = Array.from(
                        document.querySelectorAll(".mindmap-category")
                    );

                    const draggedIndex =
                        categories.indexOf(draggedCategory);
                    const targetIndex = categories.indexOf(category);

                    const rect = category.getBoundingClientRect();
                    const insertAfter =
                        event.clientY >= rect.top + rect.height / 2;

                        let position = targetIndex;

                        if (insertAfter) {
                            position += 1;
                        }

                        if (draggedIndex < position) {
                            position -= 1;
                        }

                        const uncategorisedCategory = categories.find(
                            function (item) {
                                return (
                                    item.querySelector("h3")?.textContent.trim() ===
                                    "Uncategorised"
                                );
                            }
                        );

                        if (uncategorisedCategory) {
                            const uncategorisedIndex =
                                categories.indexOf(uncategorisedCategory);

                            if (position <= uncategorisedIndex) {
                                position = uncategorisedIndex + 1;
                            }
                        }

                    let response;

                    try {
                        response = await fetch(
                            `/mindmap-categories/${categoryId}/move`,
                            {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json"
                                },
                                body: JSON.stringify({
                                    position: position
                                })
                            }
                        );
                    } catch (error) {
                        showNotification(
                            "Move failed: network error.",
                            true
                        );
                        return;
                    }

                    if (!response.ok) {
                        const serverError = await readErrorMessage(
                            response,
                            "The category could not be moved."
                        );

                        showNotification(
                            `Move failed: ${serverError}`,
                            true
                        );
                        return;
                    }

                        const orderedCategories = Array.from(
                            document.querySelectorAll(".mindmap-category")
                        );

                        const newIndex =
                            position > draggedIndex
                                ? position + 1
                                : position;

                        if (newIndex < orderedCategories.length) {
                            category.parentElement.insertBefore(
                                draggedCategory,
                                orderedCategories[newIndex]
                            );
                        } else {
                            category.parentElement.append(draggedCategory);
                        }

                    return;
                }

                const mindmapId =
                    event.dataTransfer.getData("text/plain");

                if (!mindmapId) {
                    return;
                }

                const categoryName = category
                    .querySelector("h3")
                    .textContent.trim();

                let response;

                try {
                    response = await fetch(
                        `/mindmaps/${mindmapId}/move`,
                        {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                category: categoryName
                            })
                        }
                    );
                } catch (error) {
                    showNotification(
                        "Move failed: network error.",
                        true
                    );
                    return;
                }

                if (!response.ok) {
                    const serverError = await readErrorMessage(
                        response,
                        "The map could not be moved."
                    );

                    showNotification(
                        `Move failed: ${serverError}`,
                        true
                    );
                    return;
                }

                const mapItem = document.querySelector(
                    `.mindmap-item[data-mindmap-id="${mindmapId}"]`
                );

                if (!mapItem) {
                    return;
                }

                category
                    .querySelector(".mindmap-list")
                    .append(mapItem);

                if (String(mindmapId) === String(currentMindmapId)) {
                    currentMindmapCategory = categoryName;
                }
            });
        });

const deleteTarget =
    document.querySelector("#mindmap-delete-target");

deleteTarget.addEventListener("dragover", function (event) {
    if (event.dataTransfer.types.includes("text/plain")) {
        event.preventDefault();
        deleteTarget.classList.add("drag-over");
    }
});

deleteTarget.addEventListener("dragleave", function () {
    deleteTarget.classList.remove("drag-over");
});

deleteTarget.addEventListener("drop", async function (event) {
    event.preventDefault();
    deleteTarget.classList.remove("drag-over");

    const mindmapId =
        event.dataTransfer.getData("text/plain");

    if (!mindmapId) {
        return;
    }

    let response;

    try {
        response = await fetch(
            `/mindmaps/${mindmapId}/delete`,
            {
                method: "POST"
            }
        );
    } catch (error) {
        showNotification("Delete failed: network error.", true);
        return;
    }

    if (!response.ok) {
        const serverError = await readErrorMessage(
            response,
            "The map could not be deleted."
        );

        showNotification(
            `Delete failed: ${serverError}`,
            true
        );
        return;
    }

    const mapItem = document.querySelector(
        `.mindmap-item[data-mindmap-id="${mindmapId}"]`
    );

    if (mapItem) {
        mapItem.remove();
    }

    if (currentMindmapId === Number(mindmapId)) {
        currentMindmapId = null;
        currentMindmapCategory = "Uncategorised";
        document.querySelector("#mindmap-empty").style.display =
            "flex";
    }
});

    document
        .querySelectorAll(".mindmap-category h3")
        .forEach(function (heading) {
            const category = heading.textContent.trim();
            const storageKey = `mindmap-category-collapsed:${category}`;

            if (localStorage.getItem(storageKey) === "true") {
                heading.parentElement.classList.add("collapsed");
            }

            heading.addEventListener("click", function () {
                const categoryElement =
                    heading.closest(".mindmap-category");
                const collapsed =
                    categoryElement.classList.toggle("collapsed");

                localStorage.setItem(
                    storageKey,
                    collapsed ? "true" : "false"
                );
            });
        });

document
    .querySelectorAll(".mindmap-category")
    .forEach(function (category) {
        const menuButton =
            category.querySelector(".mindmap-category-menu");

        if (!menuButton) {
            return;
        }

        menuButton.addEventListener("click", function (event) {
            event.stopPropagation();

            const existingMenu =
                category.querySelector(".mindmap-category-actions");

            if (existingMenu) {
                existingMenu.remove();
                return;
            }

            const menu = document.createElement("div");
            menu.className = "mindmap-category-actions";

            menu.innerHTML = `
                <button type="button">Rename</button>
                <button type="button">Delete</button>
            `;

            menu
                .querySelector("button:first-child")
                .addEventListener("click", async function () {
                    const categoryId = category.dataset.categoryId;
                    const heading = category.querySelector("h3");
                    const currentName = heading.textContent.trim();

                    const name = await alfPrompt(
                        "Rename category:",
                        currentName
                    );

                    if (name === null) {
                        return;
                    }

                    const trimmedName = name.trim();

                    if (!trimmedName || trimmedName === currentName) {
                        return;
                    }

                    let response;

                    try {
                        response = await fetch(
                            `/mindmap-categories/${categoryId}`,
                            {
                                method: "PATCH",
                                headers: {
                                    "Content-Type": "application/json"
                                },
                                body: JSON.stringify({
                                    name: trimmedName
                                })
                            }
                        );
                    } catch (error) {
                        showNotification(
                            "Rename failed: network error.",
                            true
                        );
                        return;
                    }

                    if (!response.ok) {
                        const serverError = await readErrorMessage(
                            response,
                            "The category could not be renamed."
                        );

                        showNotification(
                            `Rename failed: ${serverError}`,
                            true
                        );
                        return;
                    }

                    heading.textContent = trimmedName;
                    menu.remove();
                });

            menu
                .querySelector("button:last-child")
                .addEventListener("click", async function () {
                    const categoryId = category.dataset.categoryId;

                    let response;

                    try {
                        response = await fetch(
                            `/mindmap-categories/${categoryId}`,
                            {
                                method: "DELETE"
                            }
                        );
                    } catch (error) {
                        showNotification(
                            "Delete failed: network error.",
                            true
                        );
                        return;
                    }

                    if (!response.ok) {
                        const serverError = await readErrorMessage(
                            response,
                            "The category could not be deleted."
                        );

                        showNotification(
                            `Delete failed: ${serverError}`,
                            true
                        );
                        return;
                    }

                    category.remove();
                });

            category.append(menu);
        });
    });

async function openMindmapItem(item) {
    const mindmapId = item.dataset.mindmapId;

    let response;

    try {
        response = await fetch(
            `/mindmaps/${mindmapId}`
        );
    } catch (error) {
        showNotification("Open failed: network error.", true);
        return;
    }

    if (!response.ok) {
        const serverError = await readErrorMessage(
            response,
            "The map could not be opened."
        );

        showNotification(
            `Open failed: ${serverError}`,
            true
        );
        return;
    }

    const savedMindmap = await response.json();
    const savedContent = JSON.parse(
        savedMindmap.content
    );

    currentMindmapId = savedMindmap.id;
    currentMindmapCategory = savedMindmap.category;

    document.querySelector("#mindmap-empty").style.display =
        "none";

    mindmap.show(savedContent);
    mindmap.select_node("root");
    mindmap.view.e_panel.focus();
}

function bindMindmapItemClick(item) {
    item.addEventListener("click", function () {
        openMindmapItem(item);
    });
}

document
    .querySelectorAll(".mindmap-item")
    .forEach(bindMindmapItemClick);
