# Send to Kindle GitHub Action

Package clipped Markdown articles from an Obsidian vault into individual EPUBs and send them to Kindle.

This repository is both:

- A reusable GitHub Action for an Obsidian vault repository.
- A small Python CLI that can be run locally while developing.

The intended setup is:

```text
Obsidian vault repo -> scheduled GitHub workflow -> this action -> one Kindle email per article
```

## Use In Your Vault

Create this file in your Obsidian vault repository:

```text
.github/workflows/send-to-kindle.yml
```

Use:

```yaml
name: Send articles to Kindle

on:
  workflow_dispatch:
  schedule:
    - cron: "17 14 * * *"

permissions:
  contents: write

concurrency:
  group: send-to-kindle
  cancel-in-progress: false

jobs:
  send:
    runs-on: ubuntu-latest
    env:
      EARLIEST_CREATED: ${{ vars.EARLIEST_CREATED }}
      SMTP_HOST: ${{ vars.SMTP_HOST }}
      SMTP_PORT: ${{ vars.SMTP_PORT }}

    steps:
      - name: Check out vault
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Send articles
        uses: Pajdzik/send-to-kindle-github-action@v5
        with:
          articles-path: Articles
          title: Kamilpedia Articles
          author: Kamil
          earliest-created: ${{ vars.EARLIEST_CREATED }}
          limit: ${{ vars.KINDLE_ARTICLE_LIMIT || '1' }}
          kindle-email: ${{ vars.KINDLE_EMAIL }}
          from-email: ${{ vars.FROM_EMAIL }}
          smtp-user: ${{ vars.SMTP_USER }}
          smtp-password: ${{ secrets.SMTP_PASSWORD }}
```

An example is also available at [examples/vault-workflow.yml](examples/vault-workflow.yml).

## Required Variables And Secrets

Add these repository variables to the vault repository, not this action repository:

```text
KINDLE_EMAIL
FROM_EMAIL
SMTP_USER
SMTP_HOST
SMTP_PORT
EARLIEST_CREATED
KINDLE_ARTICLE_LIMIT
```

`FROM_EMAIL` must be approved in Amazon Kindle Personal Document Settings.

Add this repository secret:

```text
SMTP_PASSWORD
```

For Gmail or Outlook.com, use an app password for `SMTP_PASSWORD`.

For Outlook.com:

```text
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
```

To skip old backlog, set `EARLIEST_CREATED` to a date such as:

```text
EARLIEST_CREATED=2026-05-01
```

To tune the number of article emails per run:

```text
KINDLE_ARTICLE_LIMIT=1
```

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `articles-path` | `Articles` | Folder inside the checked-out vault that contains clipped Markdown articles. |
| `base-file` | empty | Optional Obsidian `.base` file path to use as a selection hint. |
| `earliest-created` | empty | Earliest article frontmatter `created` date to consider, in `YYYY-MM-DD` format. If omitted, `EARLIEST_CREATED` env var is used. |
| `limit` | `10` | Maximum article emails per run. Use `0` for unlimited. |
| `title` | `Obsidian Articles` | Reserved for future bundled mode. Individual EPUBs use article titles. |
| `author` | `Obsidian` | EPUB author. |
| `state-path` | `.send-to-kindle-state.json` | Sent-state file committed back to the vault repo. |
| `dry-run` | `false` | Build the EPUB without sending or updating state. |
| `kindle-email` | required | Send to Kindle email address. |
| `from-email` | required | Approved sender email address. |
| `smtp-host` | empty | SMTP host. If omitted, `SMTP_HOST` env var is used, then `smtp.gmail.com`. |
| `smtp-port` | empty | SMTP port. If omitted, `SMTP_PORT` env var is used, then `587`. |
| `smtp-user` | required | SMTP username. |
| `smtp-password` | required | SMTP password or app password. |
| `commit-state` | `true` | Commit the sent-state file after a successful send. |

## Article Selection

By default, the action reads every Markdown file under `articles-path`.

If `earliest-created` or `EARLIEST_CREATED` is set, files without a frontmatter `created` date are skipped, and only articles with `created` on or after the cutoff are considered.

It can also use an Obsidian `.base` file as a selection hint. [Obsidian Bases](https://obsidian.md/help/bases/syntax) are saved as `.base` files and define filters over Markdown files and properties. This action supports a practical subset:

- `file.inFolder("...")`
- `file.hasTag("...")`
- `tag contains "..."`
- simple property comparisons like `kindle == true`

If your Base uses advanced formulas, keep the action pointed at a dedicated article folder or add filtering support in the Python package.

## State

The action sends one email per selected article. Each email has one EPUB attachment, and each EPUB uses the article title as its Kindle document title.

After a successful run, the action writes article IDs to:

```text
.send-to-kindle-state.json
```

It then commits that file back to the vault repo. This prevents future scheduled runs from sending the same articles again.

## Local Development

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests
```

To run locally:

```bash
cp config.example.toml config.toml
send-to-kindle --config config.toml --dry-run
```

## Notes

- The generated EPUB is written to `out/`.
- The current Markdown renderer handles the common clipped-article subset: headings, paragraphs, lists, blockquotes, fenced code, links, bold, italic, inline code, and Obsidian wikilinks. Images are rendered as links for Kindle compatibility.
- The action expects the vault workflow to run `actions/setup-python` before calling it.
