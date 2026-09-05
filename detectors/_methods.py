"""Replace or append a '## <title>' section in docs/methods.md."""
import os, re
def write_section(title, body, path="docs/methods.md"):
    s = open(path).read() if os.path.exists(path) else "# Verity methods\n"
    pat = re.compile(rf"\n## {re.escape(title)}\n.*?(?=\n## |\Z)", re.S)
    block = f"\n## {title}\n\n{body.strip()}\n"
    s = pat.sub(block, s, count=1) if pat.search(s) else s.rstrip() + "\n" + block
    open(path, "w").write(s)
def md_table(rows, cols):
    def fmt(v):
        if v is None: return ""
        if isinstance(v, float): return f"{v:,.2f}"
        if isinstance(v, int): return f"{v:,}"
        return str(v)
    return "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n" + "\n".join("| " + " | ".join(fmt(v) for v in r) + " |" for r in rows)
