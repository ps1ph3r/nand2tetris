import sys
import re
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass


# token data structures
class TokenType(Enum):
    KEYWORD = auto()
    SYMBOL = auto()
    IDENTIFIER = auto()
    INT_CONST = auto()
    STRING_CONST = auto()


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str


# regex setup for lexer
KEYWORDS = [
    "class",
    "constructor",
    "function",
    "method",
    "field",
    "static",
    "var",
    "int",
    "char",
    "boolean",
    "void",
    "true",
    "false",
    "null",
    "this",
    "let",
    "do",
    "if",
    "else",
    "while",
    "return",
]

# exact word boundary match for keywords
KEYWORD_REGEX = r"\b(?:{})\b".format("|".join(KEYWORDS))

SYMBOLS = [
    "{",
    "}",
    "(",
    ")",
    "[",
    "]",
    ".",
    ",",
    ";",
    "+",
    "-",
    "*",
    "/",
    "&",
    "|",
    "<",
    ">",
    "=",
    "~",
]

# escape symbols so regex doesn't treat them as special characters
SYMBOL_REGEX = r"[{}]".format(re.escape("".join(SYMBOLS)))

INT_REGEX = r"\d+"

# match everything between double quotes
STRING_REGEX = r'"[^"\n]*"'

# identifiers can't start with a number
IDENTIFIER_REGEX = r"[a-zA-Z_]\w*"

# master regex using named capture groups
MASTER_REGEX = re.compile(
    f"(?P<KEYWORD>{KEYWORD_REGEX})|"
    f"(?P<SYMBOL>{SYMBOL_REGEX})|"
    f"(?P<INT_CONST>{INT_REGEX})|"
    f"(?P<STRING_CONST>{STRING_REGEX})|"
    f"(?P<IDENTIFIER>{IDENTIFIER_REGEX})"
)


# tokenizer logic
def remove_comments(raw_code: str) -> str:
    # replace block comments with a space to prevent words from fusing together
    clean_code = re.sub(r"/\*.*?\*/", " ", raw_code, flags=re.DOTALL)
    # strip single line comments
    clean_code = re.sub(r"//.*", "", clean_code)
    return clean_code


def tokenize(raw_code: str) -> list[Token]:
    clean_code = remove_comments(raw_code)
    tokens = []

    for match in MASTER_REGEX.finditer(clean_code):
        kind = match.lastgroup
        value = match.group(kind)

        # strip the quotes from string constants
        if kind == "STRING_CONST":
            value = value[1:-1]

        tokens.append(Token(TokenType[kind], value))

    return tokens


# XML Generation
def escape_xml(char: str) -> str:
    # course requires escaping these specific symbols in the XML
    mapping = {"<": "&lt;", ">": "&gt;", '"': "&quot;", "&": "&amp;"}
    return mapping.get(char, char)


def generate_xml(tokens: list[Token]) -> str:
    xml_lines = ["<tokens>"]

    for token in tokens:
        val = escape_xml(token.value)

        if token.type == TokenType.KEYWORD:
            xml_lines.append(f"<keyword> {val} </keyword>")
        elif token.type == TokenType.SYMBOL:
            xml_lines.append(f"<symbol> {val} </symbol>")
        elif token.type == TokenType.IDENTIFIER:
            xml_lines.append(f"<identifier> {val} </identifier>")
        elif token.type == TokenType.INT_CONST:
            xml_lines.append(f"<integerConstant> {val} </integerConstant>")
        elif token.type == TokenType.STRING_CONST:
            xml_lines.append(f"<stringConstant> {val} </stringConstant>")

    xml_lines.append("</tokens>")
    return "\n".join(xml_lines)


def main():
    if len(sys.argv) != 2:
        print("Usage: python JackTokenizer.py <file.jack | directory>")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if input_path.is_dir():
        jack_files = list(input_path.glob("*.jack"))
    else:
        jack_files = [input_path]

    for jack_file in jack_files:
        raw_text = jack_file.read_text()
        tokens = tokenize(raw_text)
        xml_output = generate_xml(tokens)

        output_file = jack_file.with_name(f"My{jack_file.stem}T.xml")
        output_file.write_text(xml_output + "\n")
        print(f"Generated {output_file.name}")


if __name__ == "__main__":
    main()
