from pathlib import Path
from markupsafe import Markup


def render_preview(file_path: Path) -> tuple[str, str]:
    """
    Render a file preview. Returns (html_content, preview_type).
    preview_type is one of: pdf, notebook, code, text, image, unknown
    """
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return "", "pdf"

    if ext == ".ipynb":
        return _render_notebook(file_path), "notebook"

    if ext == ".py":
        return _render_code(file_path, "python"), "code"

    if ext == ".md":
        return _render_markdown(file_path), "markdown"

    if ext in (".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".html"):
        return _render_text(file_path), "text"

    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg"):
        return "", "image"

    return "", "unknown"


def _render_notebook(file_path: Path) -> str:
    """Convert Jupyter notebook to HTML using nbconvert."""
    try:
        import nbformat
        from nbconvert import HTMLExporter

        with open(file_path, "r", encoding="utf-8") as f:
            nb = nbformat.read(f, as_version=4)

        exporter = HTMLExporter()
        exporter.template_name = "basic"
        body, _ = exporter.from_notebook_node(nb)
        return body
    except Exception as e:
        return f"<p class='text-red-500'>Error rendering notebook: {e}</p>"


def _render_code(file_path: Path, language: str = "python") -> str:
    """Syntax-highlight a source file using Pygments."""
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name
        from pygments.formatters import HtmlFormatter

        code = file_path.read_text(encoding="utf-8", errors="replace")
        lexer = get_lexer_by_name(language)
        formatter = HtmlFormatter(
            linenos=True,
            cssclass="highlight",
            style="monokai",
        )
        highlighted = highlight(code, lexer, formatter)
        css = HtmlFormatter(style="monokai").get_style_defs(".highlight")
        return f"<style>{css}</style>{highlighted}"
    except Exception as e:
        return f"<pre>Error highlighting code: {e}</pre>"


def _render_markdown(file_path: Path) -> str:
    """Render a Markdown file to HTML."""
    try:
        import re
        from html import escape

        text = file_path.read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        html_parts = []
        in_code_block = False
        code_lang = ""
        code_lines = []

        for line in lines:
            # Code blocks
            if line.strip().startswith("```"):
                if in_code_block:
                    code_text = escape("\n".join(code_lines))
                    html_parts.append(f'<pre class="bg-gray-900 text-green-300 p-4 rounded-lg overflow-x-auto text-sm my-3"><code>{code_text}</code></pre>')
                    code_lines = []
                    in_code_block = False
                else:
                    code_lang = line.strip()[3:].strip()
                    in_code_block = True
                continue

            if in_code_block:
                code_lines.append(line)
                continue

            stripped = line.strip()

            # Headings
            if stripped.startswith("#### "):
                html_parts.append(f'<h4 class="text-base font-semibold text-gray-800 mt-4 mb-1">{escape(stripped[5:])}</h4>')
            elif stripped.startswith("### "):
                html_parts.append(f'<h3 class="text-lg font-semibold text-gray-800 mt-5 mb-2">{escape(stripped[4:])}</h3>')
            elif stripped.startswith("## "):
                html_parts.append(f'<h2 class="text-xl font-bold text-gray-800 mt-6 mb-2 border-b border-gray-200 pb-1">{escape(stripped[3:])}</h2>')
            elif stripped.startswith("# "):
                html_parts.append(f'<h1 class="text-2xl font-bold text-gray-800 mt-6 mb-3">{escape(stripped[2:])}</h1>')
            elif stripped.startswith("- ") or stripped.startswith("* "):
                content = _inline_format(stripped[2:])
                html_parts.append(f'<li class="ml-4 text-gray-700 text-sm list-disc">{content}</li>')
            elif re.match(r"^\d+\.\s", stripped):
                content = _inline_format(re.sub(r"^\d+\.\s", "", stripped))
                html_parts.append(f'<li class="ml-4 text-gray-700 text-sm list-decimal">{content}</li>')
            elif stripped.startswith(">"):
                content = _inline_format(stripped[1:].strip())
                html_parts.append(f'<blockquote class="border-l-4 border-blue-300 pl-4 py-1 my-2 text-gray-600 text-sm italic">{content}</blockquote>')
            elif stripped == "---" or stripped == "***":
                html_parts.append('<hr class="my-4 border-gray-200">')
            elif stripped == "":
                html_parts.append('<div class="h-2"></div>')
            else:
                content = _inline_format(stripped)
                html_parts.append(f'<p class="text-gray-700 text-sm leading-relaxed">{content}</p>')

        return "\n".join(html_parts)
    except Exception as e:
        return f"<p class='text-red-500'>Error rendering markdown: {e}</p>"


def _inline_format(text: str) -> str:
    """Handle inline markdown: bold, italic, code, links."""
    import re
    from html import escape

    text = escape(text)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r'<strong class="font-semibold">\1</strong>', text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r'<code class="bg-gray-100 text-red-600 px-1.5 py-0.5 rounded text-xs font-mono">\1</code>', text)
    return text


def _render_text(file_path: Path) -> str:
    """Render a text file in a <pre> block."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        # Escape HTML
        from html import escape
        return f"<pre class='whitespace-pre-wrap text-sm text-gray-800 p-4 bg-gray-50 rounded-lg overflow-x-auto'>{escape(text)}</pre>"
    except Exception as e:
        return f"<pre>Error reading file: {e}</pre>"
