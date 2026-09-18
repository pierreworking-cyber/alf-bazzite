# ALF

ALF is Peter's local computing companion.

It is intended to be a long-lived, persistent system whose knowledge,
memories and capabilities can evolve over time.

ALF is not intended to become another chatbot.

## Philosophy

**The LLM is replaceable. ALF is not.**

ALF owns its identity, tools, memory, workflow and application architecture.
The local LLM is one component of that system and may be replaced without
replacing ALF itself.

ALF is designed to be:

* useful rather than impressive;
* correct rather than merely fluent;
* local and inspectable;
* evidence-aware;
* deterministic where appropriate;
* simple enough to remain understandable.

The core principles are:

* **Correctness over speed**
* **Tools over guesses**
* **Records over assumed memories**
* **Simplicity over unnecessary complexity**

## Current capabilities

ALF currently provides:

* system awareness through controlled system interfaces;
* Git repository awareness;
* persistent memory using SQLite;
* categorised memories;
* memory history and relationships;
* memory search;
* memory archiving;
* permanent memory deletion;
* in-place memory editing;
* deterministic command discovery and dispatch;
* capability discovery and self-description;
* self-inspection through the `health` command;
* external research and evidence retrieval;
* local LLM interpretation of supplied information;
* mind maps through the web interface, with connected nodes organised into categories;
* an experimental Textual TUI;
* a local web interface.

## Running ALF

After activating the Python environment:

```text
alf
```

ALF can also be run with specific commands.

For example:

```text
alf help
```

displays available commands.

Command help can be requested with:

```text
alf help <command>
```

## Current commands

The current command vocabulary includes:

* `alf about` — Explain what ALF is
* `alf archive <id>` — Archive a memory
* `alf calc` — Perform a calculation
* `alf categories` — Show memory categories
* `alf delete <id>[,<id>...]` — Permanently delete memories
* `alf health` — Show ALF internal health information
* `alf help [command]` — Show command help
* `alf history <id>` — Show memory history
* `alf memories` — Recall previous memories
* `alf memory <id>` — Show a single memory
* `alf question` — Ask ALF a question
* `alf relate` — Manage relationships between memories
* `alf remember <category> "text"` — Add a memory
* `alf search "text"` — Search memories
* `alf tui` — Launch the Textual interface
* `alf version` — Show ALF version
* `alf web` — Launch the web interface

The command dispatcher is deterministic. Unambiguous command prefixes may be
used, but ALF does not guess commands from natural language.

## Memory

ALF stores persistent memories using SQLite.

Memories currently support categories including:

* `note`
* `fact`
* `decision`
* `preference`

Memories have permanent IDs.

New memories can reference previous memories, allowing ALF to preserve the
evolution of knowledge without modifying existing records.

Memory history is based on the `previous_memory_id` chain.

For example:

```text
alf remember preference "Peter prefers structured data"
```

Memories can be archived when they are no longer active.

### Deleting memories

Memory deletion is permanent.

```text
alf delete 42
```

Deleted memories are removed from the database rather than being retained as
"forgotten" records.

Existing references to deleted memories are not silently rewritten. Historical
and relationship lookups simply ignore records that no longer exist.

### Editing memories

An existing memory can also be edited in place.

Editing does not create a new memory or revision. Creating a new memory remains
the mechanism for preserving an evolution of knowledge.

## Evidence and the local LLM

ALF does not treat the local LLM as an authoritative source of factual
knowledge.

ALF gathers information through its capabilities and evidence sources, then
the LLM interprets that information and produces a natural-language response.

The intended flow is:

**ALF gathers evidence → the LLM interprets it → ALF presents the result**

Consequently, ALF's architecture is designed so that the LLM can be replaced
without replacing the underlying application.

## Data storage

ALF separates source code from personal and runtime data.

The project uses SQLite for persistent memory.

The current development database is:

```text
~/.local/share/alf/alf.db
```

The database is not stored in version control.


## System awareness and safety

ALF's system awareness is based on explicitly permitted interfaces rather
than unrestricted shell access.

ALF must not autonomously:

* invoke `sudo`;
* elevate privileges;
* execute privileged operations;
* imply that an action has occurred when it has not.

Where privileged information is required, ALF may explain the limitation
without turning the privileged operation into an instruction for the user.

## Interfaces

ALF currently provides three interfaces:

* **CLI** — the primary interface and the reference implementation;
* **Textual TUI** — an experimental terminal interface;
* **Web** — a local web interface.

The TUI currently includes Question, Remember, Memories and Calc workspaces.

The web interface includes Question, Remember, Memories, Calc and Mind Maps workspaces.

The TUI and web interface are front-ends to the same underlying ALF
application; they do not define separate application logic.

Future interfaces should consume ALF's existing command and capability
metadata rather than maintaining separate descriptions of ALF's functionality.

## Development

ALF is early-stage development software.

The project uses:

* Python;
* SQLite;
* pytest;
* Ruff;
* Git;
* Ollama for local LLM integration.

Development deliberately favours small, understandable and testable changes.

Architectural decisions and current design direction are recorded in:

```text
WALL.md
```

The WALL is a working architectural document rather than a user manual.

## Current limitations

ALF is still evolving.

Current limitations include:

* conversational interaction remains limited;
* natural-language command interpretation is not currently part of deterministic
  command dispatch;
* autonomous planning is not implemented;
* the local LLM is not trusted as an independent knowledge provider;
* the TUI remains experimental;
* external integrations remain limited.

## Project status

**Version:** 0.2.0 development

ALF is deliberately being developed as infrastructure before attempting more
ambitious forms of intelligence.

The goal is not to accumulate features for their own sake.

The goal is to build a personal computing companion that remains reliable,
understandable, maintainable and useful as it evolves over years.
