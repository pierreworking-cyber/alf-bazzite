"""
ALF's web interface.

This module provides the Flask application used by ``alf web``.
"""
import shlex

from flask import Flask, jsonify, redirect, render_template, request, url_for
from waitress import serve

from ..calc import CalculationError, calculate
from ..command_catalogue import commands
from ..memory import (
    archive_memory,
    create_memory_category,
    create_mindmap,
    create_mindmap_category,
    delete_memory,
    delete_memory_category,
    delete_mindmap,
    delete_mindmap_category,
    find_related_memory_candidates,
    get_memories,
    get_memory_categories,
    get_memory_category,
    get_memory_query_options,
    get_mindmap,
    get_mindmap_categories,
    get_mindmaps,
    move_mindmap,
    move_mindmap_category,
    relate_memory,
    remember,
    search_memories,
    restore_memory,
    set_memory_category,
    update_memory,
    update_memory_category,
    update_mindmap,
    update_mindmap_category,
)
from ..news import (
    NewsError,
    add_feed_to_subject,
    add_subject,
    delete_feed,
    delete_subject,
    get_news_feeds,
    get_news_information,
    list_items,
    move_feed,
    refresh,
    rename_subject,
)
from ..question import answer_question

app = Flask(__name__)


@app.get("/")
def home():
    """Display the ALF web interface landing page."""
    return render_template("home.html")

@app.route("/question", methods=["GET", "POST"])
def question():
    """Display the ALF Question workspace and process questions."""

    question = ""
    verbose = False
    status = "Ready"
    answer = "Your answer will appear here."
    source = "—"

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        verbose = request.form.get("verbose") == "on"

        if question:
            status = "Asking…"

            try:
                result = answer_question(
                    question,
                    verbose=verbose,
                )

                status = "Complete"
                answer = result.answer
                source = result.source or "No reliable source"

            except Exception as error:
                status = "Failed"
                answer = "I couldn't get an answer to the question."
                source = f"Error: {error}"

    return render_template(
        "question.html",
        question=question,
        verbose=verbose,
        status=status,
        answer=answer,
        source=source,
    )

@app.get("/news")
def news():
    """Display the ALF News workspace."""

    information = get_news_information()

    subjects = information["subjects"]
    feeds = get_news_feeds()

    return render_template(
        "news.html",
        subjects=subjects,
        feeds=feeds,
    )

@app.get("/news/feed/<int:feed_id>")
def news_feed(feed_id):
    """Return recent stored news items for a feed."""

    try:
        limit = int(request.args.get("limit", 25))
        items = list_items(
            feed_id=feed_id,
            limit=limit,
        )
    except (ValueError, NewsError) as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(items)

@app.post("/news/feed/<int:feed_id>/move")
def news_feed_move(feed_id):
    """Move a news feed subscription to another subject."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No subject supplied."}), 400

    try:
        subject_id = int(data.get("subject_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid subject id."}), 400

    try:
        result = move_feed(feed_id, subject_id)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(result)

@app.delete("/news/feed/<int:feed_id>")
def news_feed_delete(feed_id):
    """Delete a news feed subscription from ALF."""
    try:
        result = delete_feed(feed_id)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(result)

@app.post("/news/subject/<int:subject_id>/feed")
def news_subject_feed_add(subject_id):
    """Add a news feed subscription to a subject."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No feed data supplied."}), 400

    try:
        result = add_feed_to_subject(
            subject_id,
            data.get("feed_url", ""),
        )
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(result)

@app.post("/news/subject/<int:subject_id>/rename")
def news_subject_rename(subject_id):
    """Rename a news subject."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No subject data supplied."}), 400

    try:
        result = rename_subject(
            subject_id,
            data.get("name", ""),
        )
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(result)

@app.delete("/news/subject/<int:subject_id>")
def news_subject_delete(subject_id):
    """Delete a news subject from ALF."""

    try:
        result = delete_subject(subject_id)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(result)

@app.post("/news/refresh")
def news_refresh():
    """Refresh stored news feeds and return the refresh result."""

    result = refresh()

    return jsonify(result)

@app.post("/news/subject")
def news_subject():
    """Create a news subject and its feed subscriptions."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No subject data supplied."}), 400

    name = data.get("name", "")
    feed_urls = data.get("feed_urls", [])

    try:
        result = add_subject(name, feed_urls)
    except Exception as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(result)

@app.route("/remember", methods=["GET", "POST"])
def remember_memory():
    """Display the ALF Remember workspace and store memories."""

    category = "note"
    content = ""
    status = "Ready"

    if request.method == "POST":
        category = request.form.get("category", "note")
        content = request.form.get("content", "").strip()

        related_memory_ids = request.form.getlist("related_memory_ids")

        if not content:
            status = "Please enter something to remember."
        else:
            result = remember(
                category,
                content,
                related_memory_ids=",".join(related_memory_ids) or None,
            )

            if result:
                status = "Memory saved."
                content = ""
            else:
                status = "I couldn't save that memory."

    return render_template(
        "remember.html",
        category=category,
        content=content,
        status=status,
    )

@app.get("/remember/related")
def remember_related():
    """Return memories related to text being composed."""

    content = request.args.get("content", "").strip()

    if not content:
        return jsonify([])

    return jsonify(find_related_memory_candidates(content))

@app.route("/memories", methods=["GET", "POST"])
def memories():
    """Display the ALF Memories workspace."""

    if request.method == "POST":
        memory_id = request.form.get("memory_id")

        content = request.form.get("content", "").strip()
        related_memory_ids = request.form.get(
            "related_memory_ids",
            "",
        ).strip()
        memory_category_id = request.form.get("memory_category_id")
        search_term = request.form.get("search", "").strip()
        preview_lines = request.form.get("preview_lines", "10")

        if memory_id and content:
            update_memory(
                int(memory_id),
                content,
            )

        if memory_id and related_memory_ids:
            relate_memory(
                int(memory_id),
                related_memory_ids,
            )

        if memory_id:
            category_id = (
                int(memory_category_id)
                if memory_category_id
                else None
            )
            set_memory_category(
                int(memory_id),
                category_id,
            )

        return redirect(
            url_for(
                "memories",
                selected=memory_id,
                memory_category=memory_category_id or None,
                search=search_term or None,
                preview_lines=preview_lines,
            )
        )

    include_archived = request.args.get("archived") == "on"
    selected_id = request.args.get("selected")
    edit_id = request.args.get("edit")
    memory_category_id = request.args.get("memory_category")
    search_term = request.args.get("search", "").strip()
    preview_lines = request.args.get("preview_lines", "10")

    if preview_lines not in {"2", "5", "10", "15"}:
        preview_lines = "10"

    preview_lines = int(preview_lines)

    options = get_memory_query_options()
    options["include_archived"] = include_archived

    if memory_category_id:
        try:
            options["memory_category_id"] = int(memory_category_id)
        except ValueError:
            memory_category_id = None

    if search_term:
        memories = search_memories(
            search_term,
            options,
        )
    else:
        memories = get_memories(options)
    memory_categories = get_memory_categories()

    category_by_id = {
        category["id"]: category
        for category in memory_categories
    }

    category_paths = {}

    def get_category_path(category_id):
        if category_id is None:
            return "Unclassified"

        if category_id in category_paths:
            return category_paths[category_id]

        category = category_by_id.get(category_id)

        if category is None:
            return "Unclassified"

        parts = [category["name"]]
        parent_id = category["parent_id"]

        while parent_id is not None:
            parent = category_by_id.get(parent_id)

            if parent is None:
                break

            parts.insert(0, parent["name"])
            parent_id = parent["parent_id"]

        path = " / ".join(parts)
        category_paths[category_id] = path

        return path

    for memory in memories:
        memory["memory_category_path"] = get_category_path(
            memory["memory_category_id"]
        )

    selected_memory = None

    if selected_id:
        try:
            selected_id = int(selected_id)
        except ValueError:
            selected_id = None

    if selected_id:
        selected_memory = next(
            (
                memory
                for memory in memories
                if memory["id"] == selected_id
            ),
            None,
        )
    return render_template(
        "memories.html",
        memories=memories,
        memory_categories=memory_categories,
        memory_category_id=options["memory_category_id"],
        include_archived=include_archived,
        search_term=search_term,
        selected_memory=selected_memory,
        edit_id=edit_id,
        preview_lines=preview_lines,
    )

@app.patch("/memories/<int:memory_id>/category")
def set_memory_category_web(memory_id):
    """Assign a memory to a category from the web interface."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No category data supplied"}), 400

    category_id = data.get("category_id")

    if category_id is None:
        return jsonify({"error": "Category ID is required"}), 400

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid category ID"}), 400

    if get_memory_category(category_id) is None:
        return jsonify({"error": "Memory category not found"}), 404

    if not set_memory_category(memory_id, category_id):
        return jsonify({"error": "Memory not found"}), 404

    return jsonify({"updated": True})

@app.post("/memory-categories")
def create_memory_category_web():
    """Create a memory category from the web interface."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No category data supplied"}), 400

    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "Category name is required"}), 400

    parent_id = data.get("parent_id")

    if parent_id is not None:
        try:
            parent_id = int(parent_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid parent category"}), 400

        if get_memory_category(parent_id) is None:
            return jsonify({"error": "Parent category not found"}), 404

    category_id = create_memory_category(
        name,
        parent_id,
    )

    if category_id == "duplicate":
        return jsonify(
            {"error": "Memory category name is already in use"}
        ), 409

    return jsonify(
        {
            "id": category_id,
            "name": name,
            "parent_id": parent_id,
        }
    )


@app.patch("/memory-categories/<int:category_id>")
def update_memory_category_web(category_id):
    """Rename a memory category."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No category data supplied"}), 400

    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "Category name is required"}), 400

    updated = update_memory_category(
        category_id,
        name,
    )

    if updated == "duplicate":
        return jsonify(
            {"error": "Memory category name is already in use"}
        ), 409

    if not updated:
        return jsonify({"error": "Memory category not found"}), 404

    return jsonify({"updated": True})


@app.delete("/memory-categories/<int:category_id>")
def delete_memory_category_web(category_id):
    """Delete a memory category."""

    deleted = delete_memory_category(category_id)

    if not deleted:
        return jsonify({"error": "Memory category not found"}), 404

    return jsonify({"deleted": True})

@app.post("/memories/archive")
def archive_memory_web():
    """Archive a memory from the web interface."""

    memory_id = request.form.get("memory_id")
    preview_lines = request.form.get("preview_lines", "10")
    memory_category_id = request.form.get("memory_category")
    include_archived = request.form.get("archived") == "on"
    search_term = request.form.get("search", "").strip()

    if memory_id:
        archive_memory(int(memory_id))

    return redirect(
        url_for(
            "memories",
            selected=memory_id,
            memory_category=memory_category_id or None,
            archived="on" if include_archived else None,
            search=search_term or None,
            preview_lines=preview_lines,
        )
    )

@app.post("/memories/restore")
def restore_memory_web():
    """Restore a memory from the web interface."""

    memory_id = request.form.get("memory_id")
    preview_lines = request.form.get("preview_lines", "10")
    memory_category_id = request.form.get("memory_category")
    include_archived = request.form.get("archived") == "on"
    search_term = request.form.get("search", "").strip()

    if memory_id:
        restore_memory(int(memory_id))

    return redirect(
        url_for(
            "memories",
            selected=memory_id,
            memory_category=memory_category_id or None,
            archived="on" if include_archived else None,
            search=search_term or None,
            preview_lines=preview_lines,
        )
    )

@app.post("/memories/delete")
def delete_memory_web():
    """Delete a memory from the web interface."""

    memory_id = request.form.get("memory_id")
    preview_lines = request.form.get("preview_lines", "10")
    memory_category_id = request.form.get("memory_category")
    include_archived = request.form.get("archived") == "on"
    search_term = request.form.get("search", "").strip()

    if memory_id:
        delete_memory(int(memory_id))

    return redirect(
        url_for(
            "memories",
            selected=memory_id,
            memory_category=memory_category_id or None,
            archived="on" if include_archived else None,
            search=search_term or None,
            preview_lines=preview_lines,
        )
    )

@app.route("/calc", methods=["GET", "POST"])
def calc():
    """Display the ALF Calculator workspace and process calculations."""

    expression = ""
    symbolic = False
    places = 3
    angle_mode = "radians"
    status = "Ready"
    result = "Your result will appear here."

    if request.method == "POST":
        expression = request.form.get("expression", "").strip()
        symbolic = request.form.get("symbolic") == "on"
        angle_mode = request.form.get("angle_mode", "radians")

        try:
            places = int(request.form.get("places", "3"))
        except ValueError:
            places = 3

        if expression:
            status = "Calculating…"

            try:
                calculation = calculate(
                    expression,
                    symbolic=symbolic,
                    places=places,
                    angle_mode=angle_mode,
                )

                status = "Complete"
                result = str(calculation)

            except CalculationError as error:
                status = "Could not calculate"
                result = str(error)

    symbolic_examples = commands["calc"]["examples"]["Symbolic mathematics"]

    examples = []

    for group_examples in commands["calc"]["examples"].values():
        for example in group_examples:
            parts = shlex.split(example)

            expression_parts = []
            example_angle_mode = "radians"

            for part in parts[2:]:
                if part == "--degrees":
                    example_angle_mode = "degrees"
                elif part == "--radians":
                    example_angle_mode = "radians"
                else:
                    expression_parts.append(part)

            expression = " ".join(expression_parts)

            examples.append(
                {
                    "expression": expression,
                    "symbolic": example in symbolic_examples,
                    "angle_mode": example_angle_mode,
                }
            )

    return render_template(
        "calc.html",
        expression=expression,
        symbolic=symbolic,
        places=places,
        angle_mode=angle_mode,
        status=status,
        result=result,
        examples=examples,
    )

@app.get("/mindmaps")
def mindmaps():
    """Display the experimental ALF Mind Maps workspace."""

    mindmaps = get_mindmaps()
    categories = get_mindmap_categories()

    return render_template(
        "mindmaps.html",
        mindmaps=mindmaps,
        categories=categories,
    )

@app.post("/mindmap-categories")
def create_mindmap_category_web():
    """Create a mind map category from the web interface."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No category data supplied"}), 400

    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "Category name is required"}), 400

    category_id = create_mindmap_category(name)

    if category_id == "duplicate":
        return jsonify(
            {"error": "Mind map category name is already in use"}
        ), 409

    return jsonify({"id": category_id, "name": name})

@app.patch("/mindmap-categories/<int:category_id>")
def update_mindmap_category_web(category_id):
    """Rename a mind map category."""

    data = request.get_json()

    if _is_uncategorised_category(category_id):
        return jsonify(
            {"error": "Uncategorised cannot be modified"}
        ), 400

    if not data:
        return jsonify({"error": "No category data supplied"}), 400

    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "Category name is required"}), 400

    updated = update_mindmap_category(
        category_id,
        name,
    )

    if updated == "duplicate":
        return jsonify(
            {"error": "Mind map category name is already in use"}
        ), 409

    if not updated:
        return jsonify({"error": "Mind map category not found"}), 404

    return jsonify({"updated": True})

@app.delete("/mindmap-categories/<int:category_id>")
def delete_mindmap_category_web(category_id):
    """Delete a mind map category."""

    if _is_uncategorised_category(category_id):
        return jsonify(
            {"error": "Uncategorised cannot be modified"}
        ), 400

    deleted = delete_mindmap_category(category_id)

    if not deleted:
        return jsonify({"error": "Mind map category not found"}), 404

    return jsonify({"deleted": True})

@app.post("/mindmaps/save")
def save_mindmap_web():
    """Save a mind map from the web interface."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No mind map data supplied"}), 400

    mindmap_id = data.get("id")
    category = data.get("category", "")
    name = data.get("name", "")
    content = data.get("content", "")

    if mindmap_id:
        if get_mindmap(int(mindmap_id)) is None:
            return jsonify({"error": "Mind map not found"}), 404

        updated = update_mindmap(
            int(mindmap_id),
            category,
            name,
            "active",
            content,
        )

        if not updated:
            return jsonify(
                {"error": "Mind map category not found"}
            ), 404
    else:
        mindmap_id = create_mindmap(
            category,
            name,
            content,
        )

    return jsonify({"id": mindmap_id})

@app.post("/mindmaps/<int:mindmap_id>/delete")
def delete_mindmap_web(mindmap_id):
    """Delete a saved mind map from the web interface."""

    deleted = delete_mindmap(mindmap_id)

    if not deleted:
        return jsonify({"error": "Mind map not found"}), 404

    return jsonify({"deleted": True})

@app.post("/mindmaps/<int:mindmap_id>/move")
def move_mindmap_web(mindmap_id):
    """Move a saved mind map to a different category."""

    data = request.get_json()

    if not data:
        return jsonify({"error": "No category supplied"}), 400

    category = data.get("category", "").strip()

    if not category:
        return jsonify({"error": "No category supplied"}), 400

    moved = move_mindmap(mindmap_id, category)

    if not moved:
        return jsonify({"error": "Mind map or category not found"}), 404

    return jsonify({"moved": True})

@app.post("/mindmap-categories/<int:category_id>/move")
def move_mindmap_category_web(category_id):
    """Move a mind map category to a different position."""

    data = request.get_json()

    if not data or "position" not in data:
        return jsonify({"error": "No position supplied"}), 400

    position = data["position"]

    if not isinstance(position, int) or position < 0:
        return jsonify({"error": "Invalid position"}), 400

    moved = move_mindmap_category(category_id, position)

    if not moved:
        return jsonify({"error": "Mind map category not found"}), 404

    return jsonify({"moved": True})

@app.get("/mindmaps/<int:mindmap_id>")
def get_mindmap_web(mindmap_id):
    """Return a saved mind map to the web interface."""

    mindmap = get_mindmap(mindmap_id)

    if mindmap is None:
        return jsonify({"error": "Mind map not found"}), 404

    return jsonify(mindmap)

def _is_uncategorised_category(category_id):
    """Return whether a category is the permanent Uncategorised category."""

    categories = get_mindmap_categories()

    return any(
        category["id"] == category_id
        and category["name"] == "Uncategorised"
        for category in categories
    )

def main() -> None:
    """Start ALF's web interface."""

    serve(app,
          host="0.0.0.0",
          port=5000,
          threads=4,
    )
