import os
import uuid
from dataclasses import dataclass

import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser


@dataclass
class CodeChunk:
    chunk_id: str          # uuid
    repo_id: str
    file_path: str         # relative to repo root, forward-slash separated
    language: str
    content: str           # the actual code text
    start_line: int        # 1-indexed, inclusive
    end_line: int          # 1-indexed, inclusive
    chunk_type: str        # "function", "class", "block", "file"
    symbol_name: str = ""  # function/class/method name if available, else ""


LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
}

# node types that represent a standalone function/method
FUNCTION_NODE_TYPES = {
    "python": {"function_definition"},
    "javascript": {"function_declaration"},
    "typescript": {"function_declaration"},
    "tsx": {"function_declaration"},
    "go": {"function_declaration", "method_declaration"},
}

# node types that represent a class-like construct with a body of members
CLASS_NODE_TYPES = {
    "python": {"class_definition"},
    "javascript": {"class_declaration"},
    "typescript": {"class_declaration"},
    "tsx": {"class_declaration"},
    "java": {"class_declaration", "interface_declaration", "enum_declaration"},
}

# node types found inside a class body that count as an individual method chunk
METHOD_NODE_TYPES = {
    "python": {"function_definition"},
    "javascript": {"method_definition"},
    "typescript": {"method_definition"},
    "tsx": {"method_definition"},
    "java": {"method_declaration", "constructor_declaration"},
}

# wrapper node types to see through when classifying a top-level statement,
# mapped to the field name holding the wrapped declaration
WRAPPER_FIELD = {
    "decorated_definition": "definition",  # python decorators
    "export_statement": "declaration",     # js/ts export / export default
}

# languages where `const foo = () => {...}` style declarations are also
# treated as function chunks
ARROW_CONST_LANGUAGES = {"javascript", "typescript", "tsx"}
ARROW_FUNCTION_VALUE_TYPES = {"arrow_function", "function", "function_expression"}

# top-level node types that are pure imports/package declarations — a run of
# leftover statements consisting only of these is noise, not worth a chunk
IMPORT_NODE_TYPES = {
    "python": {"import_statement", "import_from_statement", "future_import_statement"},
    "javascript": {"import_statement"},
    "typescript": {"import_statement"},
    "tsx": {"import_statement"},
    "java": {"import_declaration", "package_declaration"},
    "go": {"import_declaration", "package_clause"},
}
COMMENT_NODE_TYPES = {"comment", "line_comment", "block_comment"}

SLIDING_WINDOW_LINES = 50
SLIDING_WINDOW_OVERLAP = 10

_LANGUAGE_BUILDERS = {
    "python": tree_sitter_python.language,
    "javascript": tree_sitter_javascript.language,
    "typescript": tree_sitter_typescript.language_typescript,
    "tsx": tree_sitter_typescript.language_tsx,
    "java": tree_sitter_java.language,
    "go": tree_sitter_go.language,
}

_parsers: dict[str, Parser] = {}


def _get_parser(language: str) -> Parser:
    parser = _parsers.get(language)
    if parser is None:
        ts_language = Language(_LANGUAGE_BUILDERS[language]())
        parser = Parser(ts_language)
        _parsers[language] = parser
    return parser


def _node_text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _make_chunk(
    node: Node,
    source: bytes,
    repo_id: str,
    rel_path: str,
    language: str,
    chunk_type: str,
    symbol_name: str,
) -> CodeChunk:
    return CodeChunk(
        chunk_id=str(uuid.uuid4()),
        repo_id=repo_id,
        file_path=rel_path,
        language=language,
        content=_node_text(node, source),
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        chunk_type=chunk_type,
        symbol_name=symbol_name,
    )


def _unwrap(node: Node) -> Node:
    field_name = WRAPPER_FIELD.get(node.type)
    if field_name is None:
        return node
    inner = node.child_by_field_name(field_name)
    return inner if inner is not None else node


def _name_of(node: Node, source: bytes) -> str:
    name_node = node.child_by_field_name("name")
    return _node_text(name_node, source) if name_node is not None else ""


def _extract_methods(
    class_body: Node,
    source: bytes,
    repo_id: str,
    rel_path: str,
    language: str,
    class_name: str,
) -> list[CodeChunk]:
    method_types = METHOD_NODE_TYPES.get(language, set())
    chunks = []
    for child in class_body.children:
        outer = child
        inner = _unwrap(child)
        if inner.type not in method_types:
            continue
        method_name = _name_of(inner, source)
        symbol_name = f"{class_name}.{method_name}" if method_name else class_name
        chunks.append(_make_chunk(outer, source, repo_id, rel_path, language, "function", symbol_name))
    return chunks


def _extract_arrow_const(
    node: Node,
    source: bytes,
    repo_id: str,
    rel_path: str,
    language: str,
) -> list[CodeChunk]:
    chunks = []
    for declarator in node.children:
        if declarator.type != "variable_declarator":
            continue
        value = declarator.child_by_field_name("value")
        if value is None or value.type not in ARROW_FUNCTION_VALUE_TYPES:
            continue
        name = _name_of(declarator, source)
        chunks.append(_make_chunk(declarator, source, repo_id, rel_path, language, "function", name))
    return chunks


def chunk_file(file_path: str, repo_root: str, repo_id: str) -> list[CodeChunk]:
    """
    Parse file with tree-sitter, extract top-level declarations as chunks.
    Fall back to sliding window if parsing fails or the language has no grammar.
    """
    ext = os.path.splitext(file_path)[1].lower()
    rel_path = os.path.relpath(file_path, repo_root).replace(os.sep, "/")
    language = LANGUAGE_MAP.get(ext)

    with open(file_path, "rb") as f:
        source = f.read()

    if language is None:
        return sliding_window_chunk(
            source.decode("utf-8", errors="replace"), file_path, repo_root, repo_id, ext.lstrip(".") or "text"
        )

    try:
        parser = _get_parser(language)
        tree = parser.parse(source)
        root = tree.root_node
    except Exception:
        return sliding_window_chunk(
            source.decode("utf-8", errors="replace"), file_path, repo_root, repo_id, language
        )

    function_types = FUNCTION_NODE_TYPES.get(language, set())
    class_types = CLASS_NODE_TYPES.get(language, set())
    import_types = IMPORT_NODE_TYPES.get(language, set())

    chunks: list[CodeChunk] = []
    leftover: list[Node] = []

    def flush_leftover():
        if not leftover:
            return
        if all(n.type in import_types or n.type in COMMENT_NODE_TYPES for n in leftover):
            leftover.clear()
            return
        first, last = leftover[0], leftover[-1]
        chunks.append(CodeChunk(
            chunk_id=str(uuid.uuid4()),
            repo_id=repo_id,
            file_path=rel_path,
            language=language,
            content=source[first.start_byte:last.end_byte].decode("utf-8", errors="replace"),
            start_line=first.start_point[0] + 1,
            end_line=last.end_point[0] + 1,
            chunk_type="block",
            symbol_name="",
        ))
        leftover.clear()

    for child in root.children:
        outer = child
        inner = _unwrap(child)

        if inner.type in function_types:
            flush_leftover()
            name = _name_of(inner, source)
            chunks.append(_make_chunk(outer, source, repo_id, rel_path, language, "function", name))

        elif inner.type in class_types:
            flush_leftover()
            name = _name_of(inner, source)
            chunks.append(_make_chunk(outer, source, repo_id, rel_path, language, "class", name))
            body = inner.child_by_field_name("body")
            if body is not None:
                chunks.extend(_extract_methods(body, source, repo_id, rel_path, language, name))

        elif language in ARROW_CONST_LANGUAGES and outer.type in ("lexical_declaration", "variable_declaration"):
            arrow_chunks = _extract_arrow_const(outer, source, repo_id, rel_path, language)
            if arrow_chunks:
                flush_leftover()
                chunks.extend(arrow_chunks)
            else:
                leftover.append(outer)

        else:
            leftover.append(outer)

    flush_leftover()

    if not chunks:
        return sliding_window_chunk(
            source.decode("utf-8", errors="replace"), file_path, repo_root, repo_id, language
        )

    return chunks


def sliding_window_chunk(
    content: str, file_path: str, repo_root: str, repo_id: str, language: str
) -> list[CodeChunk]:
    """
    Fallback: split by lines into chunks of ~50 lines with 10-line overlap.
    """
    rel_path = os.path.relpath(file_path, repo_root).replace(os.sep, "/")
    lines = content.split("\n")
    if not lines or (len(lines) == 1 and not lines[0]):
        return []

    chunks = []
    step = SLIDING_WINDOW_LINES - SLIDING_WINDOW_OVERLAP
    start = 0
    while start < len(lines):
        end = min(start + SLIDING_WINDOW_LINES, len(lines))
        chunk_lines = lines[start:end]
        chunks.append(CodeChunk(
            chunk_id=str(uuid.uuid4()),
            repo_id=repo_id,
            file_path=rel_path,
            language=language,
            content="\n".join(chunk_lines),
            start_line=start + 1,
            end_line=end,
            chunk_type="block",
            symbol_name="",
        ))
        if end == len(lines):
            break
        start += step
    return chunks
