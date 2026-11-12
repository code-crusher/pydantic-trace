The Pydantic documentation is available in the [llms.txt](https://llmstxt.org/) format.
This format is defined in Markdown and suited for large language models.

Two formats are available:

* [llms.txt](https://pydantic.dev/docs/validation/latest/llms.txt): a file containing a brief description
  of the project, along with links to the different sections of the documentation. The structure
  of this file is described in details in the [format documentation](https://llmstxt.org/#format).
* [llms-full.txt](https://pydantic.dev/docs/validation/latest/llms-full.txt): Similar to the `llms.txt` file,
  but every link content is included. Note that this file may be too large for some LLMs.

As of today, these files *cannot* be natively leveraged by LLM frameworks or IDEs. Alternatively,
an [MCP server](https://modelcontextprotocol.io/) can be implemented to properly parse the `llms.txt`
file.

Where `llms.txt` gives an AI tool the Pydantic *documentation*, the
[Logfire MCP server](https://pydantic.dev/docs/logfire/guides/mcp-server/) gives it your
application's *runtime data*: an agent can query the traces, metrics, and recorded validations from your
own service and, for example, pull up the input behind a [`ValidationError`][pydantic_core.ValidationError]
while it's helping you fix it.

## Agent skills

Pydantic also ships an agent skill describing how to use the library. It is bundled inside the
installed package, at `pydantic/.agents/skills/pydantic/SKILL.md`, so the skill always matches the
installed Pydantic version.

To expose it to your agent, link it into your project's skills directory with
[`library-skills`](https://github.com/tiangolo/library-skills):

```bash
uvx library-skills
```

The tool discovers the skill from your installed dependencies and creates a symlink in
`.agents/skills` (or `.claude/skills` for Claude Code), so it stays up to date when you upgrade
Pydantic.
