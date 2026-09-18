"""
Command catalogue for ALF.

This module contains the metadata used to describe ALF's command
vocabulary, including help text, usage, options, examples, and
TUI-specific guidance.

The catalogue is declarative: command implementations do not live here.
Other parts of ALF use this metadata to present and discover commands
consistently.
"""

commands = {
    "help": {
        "id": "command.help",
        "help": "Show command help.",
        "usage": "alf help [command]",
        "examples": [
            "alf help",
            "alf help search",
            "alf help remember",
        ],
    },
    "calc": {
        "id": "math.calculate",
        "help": "Calculate a mathematical expression.",
        "usage": 'alf calc "expression" [options]',
        "options": {
            "--symbolic": "Evaluate the expression symbolically.",
            "--places <n>": (
                "Display a numeric result to n decimal places (1-10). "
                "Defaults to 3. The option may be abbreviated as --pla."
            ),
            "--degrees": (
                "Evaluate trigonometric functions in degrees. "
                "The option may be abbreviated as --deg."
            ),
            "--radians": (
                "Evaluate trigonometric functions in radians. "
                "This is the default. The option may be abbreviated as --rad."
            ),
        },
        "examples": {
            "Arithmetic": [
                'alf calc "12 * 7"',
                'alf calc "2^8"',
                'alf calc "sqrt(144) + 3"',
            ],
            "Trigonometry": [
                'alf calc "sin(pi / 2)"',
                'alf calc "sin(90)" --degrees',
                'alf calc "cos(0)"',
                'alf calc "tan(pi / 4)"',
                'alf calc "cos(180)" --degrees',
                'alf calc "tan(45)" --degrees',
            ],
            "Functions": [
                'alf calc "log(E)"',
                'alf calc "abs(-42)"',
                'alf calc "gcd(84, 18)"',
            ],
            "Symbolic mathematics": [
                'alf calc "solve(x^2 - 4, x)"',
                'alf calc "expand((x + 2)^2)"',
                'alf calc "factor(x^2 - 4)"',
                'alf calc "diff(x^3, x)"',
                'alf calc "integrate(x^2, x)"',
                'alf calc "limit(sin(x) / x, x, 0)"',
                'alf calc "simplify((x^2 - 1)/(x - 1))"',
                'alf calc "solve(x^2 + 5*x + 6, x)"',
                'alf calc "expand((x + 3)^3)"',
            ],
        },
        "tui": {
            "title": "Calculator",
            "description": "Enter a mathematical expression.",
            "guidance": (
                "ALF can work with arithmetic, algebra, functions, "
                "equations, and calculus."
            ),
        },
    },
    "remember": {
        "id": "memory.add",
        "help": "Add a memory.",
        "usage": 'alf remember <category> "text" [options]',
        "options": {
            "-c, --category <name>": "Specify the memory category.",
            "-r, --relate <ids>": "Relate this memory to existing memory IDs.",
        },
        "notes": [
            "View available categories with: alf categories",
            "The category may also be given positionally.",
            "Options may appear before or after the memory text.",
        ],
        "examples": [
            'alf remember preference "Peter prefers dogs"',
            'alf remember "Peter prefers dogs" --category preference',
            'alf remember -c preference "Peter prefers dogs"',
            'alf remember preference "Peter prefers Labradors" --relate 4,12',
            'alf remember -c preference "Peter prefers Labradors" -r 4,12',
        ],
        "tui": {
            "title": "Remember",
            "description": "Give ALF something to remember.",
            "guidance": (
                "Choose a category, enter the memory, and optionally "
                "relate it to existing memories."
            ),
        },
    },
    "relate": {
        "id": "memory.relate",
        "help": "Relate an existing memory to other memories.",
        "usage": "alf relate <id> <ids>",
        "notes": [
            "Relationships are directional.",
            "Existing relationships are preserved.",
            "Duplicate relationships are ignored.",
        ],
        "examples": [
            "alf relate 47 46",
            "alf relate 47 46,43",
        ],
    },
    "memories": {
        "id": "memory.list",
        "help": "Recall previous memories.",
        "usage": "alf memories",
        "options": {
            "--all": "Include archived memories.",
            "--category <name>": "Restrict results to a memory category.",
            "--group <name>": "Group memories by a field.",
        },
        "examples": [
            "alf memories",
            "alf memories --all",
            "alf memories --category preference",
            "alf memories --group category",
        ],
        "tui": {
            "title": "Memories",
            "description": "Recall and explore previous memories.",
            "guidance": "Select a memory to view its details.",
        },
    },
    "categories": {
        "id": "memory.categories",
        "help": "Show memory categories.",
        "usage": "alf categories",
    },
    "memory": {
        "id": "memory.show",
        "help": "Show a single memory.",
        "usage": "alf memory <id>",
        "examples": [
            "alf memory 11",
        ],
    },
    "history": {
        "id": "memory.history",
        "help": "Show memory history.",
        "usage": "alf history <id>",
        "examples": [
            "alf history 11",
        ],
    },
    "health": {
        "id": "system.health",
        "help": "Show ALF internal health information.",
        "usage": "alf health [--details]",
        "options": {
            "--details": "Show detailed health information.",
        },
    },
    "about": {
        "id": "identity.about",
        "help": "Explain what ALF is.",
        "usage": "alf about [--details]",
        "options": {
            "--details": "Show extended identity information.",
        },
        "examples": [
            "alf about",
            "alf about --details",
        ],
    },
    "archive": {
        "id": "memory.archive",
        "help": "Archive one or more memories.",
        "usage": "alf archive <id>[,<id>...]",
        "examples": [
            "alf archive 11",
            "alf archive 10-12",
            "alf archive 10-12,15,20-21",
        ],
    },
    "delete": {
        "id": "memory.delete",
        "help": "Delete one or more memories.",
        "usage": "alf delete <id>[,<id>...]",
        "examples": [
            "alf delete 10-12",
            "alf delete 15",
            "alf delete 20-21",
            "alf delete 10-12,15,20-21",
        ],
    },
    "version": {
        "id": "identity.version",
        "help": "Show ALF version.",
        "usage": "alf version",
    },
    "search": {
        "id": "memory.search",
        "help": "Search memories.",
        "usage": 'alf search "text"',
        "options": {
            "--all": "Include archived memories.",
            "--category <name>": "Restrict results to a memory category.",
        },
        "examples": [
            "alf search bananas",
            "alf search bananas --all",
            "alf search Peter --category preference",
        ],
    },
    "question": {
        "id": "llm.question",
        "help": "Ask ALF a question.",
        "usage": 'alf question [-v, --verbose] "text"',
        "options": {
            "-v, --verbose": "Give a more detailed answer.",
        },
        "examples": [
            'alf question "What is the capital of Morocco?"',
            'alf question -v "Why does the Moon look larger near the horizon?"',
        ],
        "notes": [
            "Quote the entire question so the shell passes it to ALF as one argument.",
        ],
        "tui": {
            "title": "Question",
            "description": "Ask ALF a question.",
            "guidance": (
                "Enter your question and choose whether you want "
                "a detailed answer."
            ),
        },
    },
    "tui": {
        "id": "interface.tui",
        "help": "Launch the ALF terminal user interface.",
        "usage": "alf tui",
        "examples": [
            "alf tui",
        ],
    },
    "web": {
        "id": "interface.web",
        "help": "Launch the ALF web interface.",
        "usage": "alf web",
        "examples": [
            "alf web",
        ],
    },
    "news": {
        "id": "news.manage",
        "help": "Manage ALF's subscribed news subjects.",
        "usage": "alf news <command> [arguments]",
        "notes": [
            "Commands: add, refresh, list, query, status",
            "The news service is provided by Miniflux.",
            "For news add, the first argument is the subject name.",
        ],
        "examples": [
            'alf news add "World News" "https://feeds.bbci.co.uk/news/world/rss.xml"',
            'alf news refresh',
            'alf news refresh "Ukraine"',
            'alf news list',
            'alf news list "Ukraine" --days 7',
            'alf news query "Ukraine" --days 7 --limit 10',
            'alf news status',
        ],
    },
}
