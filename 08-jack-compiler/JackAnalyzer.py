import sys
import re
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Union


# Lexical Analysis (Tokenizer)
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
SYMBOL_REGEX = r"[{}]".format(re.escape("".join(SYMBOLS)))
INT_REGEX = r"\d+"
STRING_REGEX = r'"[^"\n]*"'
IDENTIFIER_REGEX = r"[a-zA-Z_]\w*"

MASTER_REGEX = re.compile(
    f"(?P<KEYWORD>{KEYWORD_REGEX})|"
    f"(?P<SYMBOL>{SYMBOL_REGEX})|"
    f"(?P<INT_CONST>{INT_REGEX})|"
    f"(?P<STRING_CONST>{STRING_REGEX})|"
    f"(?P<IDENTIFIER>{IDENTIFIER_REGEX})"
)


def remove_comments(raw_code: str) -> str:
    clean_code = re.sub(r"/\*.*?\*/", " ", raw_code, flags=re.DOTALL)
    clean_code = re.sub(r"//.*", "", clean_code)
    return clean_code


def tokenize(raw_code: str) -> list[Token]:
    clean_code = remove_comments(raw_code)
    tokens = []
    for match in MASTER_REGEX.finditer(clean_code):
        kind = match.lastgroup
        value = match.group(kind)
        if kind == "STRING_CONST":
            value = value[1:-1]
        tokens.append(Token(TokenType[kind], value))
    return tokens


# Syntax Analysis - AST & Parser
@dataclass
class Terminal:
    token: Token


@dataclass
class NonTerminal:
    name: str
    children: list[Union["NonTerminal", Terminal]] = field(default_factory=list)


class CompilationEngine:
    """Recursive Descent Parser that builds an AST from a list of Tokens."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.idx = 0

    def has_more(self) -> bool:
        return self.idx < len(self.tokens)

    def peek(self, offset: int = 0) -> Token | None:
        if self.idx + offset < len(self.tokens):
            return self.tokens[self.idx + offset]
        return None

    def advance(self) -> Terminal:
        token = self.tokens[self.idx]
        self.idx += 1
        return Terminal(token)

    def consume(
        self, expected_value: str = None, expected_type: TokenType = None
    ) -> Terminal:
        token = self.peek()
        if not token:
            raise SyntaxError("Unexpected end of file")
        if expected_type and token.type != expected_type:
            raise SyntaxError(
                f"Expected type {expected_type}, got {token.type} ('{token.value}')"
            )
        if expected_value and token.value != expected_value:
            raise SyntaxError(f"Expected '{expected_value}', got '{token.value}'")
        return self.advance()

    # Grammar rules

    def compile_class(self) -> NonTerminal:
        node = NonTerminal("class")
        node.children.append(self.consume("class"))
        node.children.append(self.consume(expected_type=TokenType.IDENTIFIER))
        node.children.append(self.consume("{"))

        while self.has_more() and self.peek().value in ["static", "field"]:
            node.children.append(self.compile_class_var_dec())

        while self.has_more() and self.peek().value in [
            "constructor",
            "function",
            "method",
        ]:
            node.children.append(self.compile_subroutine())

        node.children.append(self.consume("}"))
        return node

    def compile_class_var_dec(self) -> NonTerminal:
        node = NonTerminal("classVarDec")
        node.children.append(self.advance())  # static or field
        node.children.append(self.advance())  # type
        node.children.append(
            self.consume(expected_type=TokenType.IDENTIFIER)
        )  # varName

        while self.peek().value == ",":
            node.children.append(self.consume(","))
            node.children.append(self.consume(expected_type=TokenType.IDENTIFIER))

        node.children.append(self.consume(";"))
        return node

    def compile_subroutine(self) -> NonTerminal:
        node = NonTerminal("subroutineDec")
        node.children.append(self.advance())  # constructor, function, or method
        node.children.append(self.advance())  # void or type
        node.children.append(
            self.consume(expected_type=TokenType.IDENTIFIER)
        )  # subroutineName
        node.children.append(self.consume("("))
        node.children.append(self.compile_parameter_list())
        node.children.append(self.consume(")"))

        # Subroutine Body
        body = NonTerminal("subroutineBody")
        body.children.append(self.consume("{"))
        while self.peek().value == "var":
            body.children.append(self.compile_var_dec())
        body.children.append(self.compile_statements())
        body.children.append(self.consume("}"))

        node.children.append(body)
        return node

    def compile_parameter_list(self) -> NonTerminal:
        node = NonTerminal("parameterList")
        if self.peek().value != ")":
            node.children.append(self.advance())  # type
            node.children.append(
                self.consume(expected_type=TokenType.IDENTIFIER)
            )  # varName
            while self.peek().value == ",":
                node.children.append(self.consume(","))
                node.children.append(self.advance())
                node.children.append(self.consume(expected_type=TokenType.IDENTIFIER))
        return node

    def compile_var_dec(self) -> NonTerminal:
        node = NonTerminal("varDec")
        node.children.append(self.consume("var"))
        node.children.append(self.advance())  # type
        node.children.append(
            self.consume(expected_type=TokenType.IDENTIFIER)
        )  # varName
        while self.peek().value == ",":
            node.children.append(self.consume(","))
            node.children.append(self.consume(expected_type=TokenType.IDENTIFIER))
        node.children.append(self.consume(";"))
        return node

    def compile_statements(self) -> NonTerminal:
        node = NonTerminal("statements")
        while self.has_more() and self.peek().value in [
            "let",
            "if",
            "while",
            "do",
            "return",
        ]:
            val = self.peek().value
            if val == "let":
                node.children.append(self.compile_let())
            elif val == "if":
                node.children.append(self.compile_if())
            elif val == "while":
                node.children.append(self.compile_while())
            elif val == "do":
                node.children.append(self.compile_do())
            elif val == "return":
                node.children.append(self.compile_return())
        return node

    def compile_let(self) -> NonTerminal:
        node = NonTerminal("letStatement")
        node.children.append(self.consume("let"))
        node.children.append(self.consume(expected_type=TokenType.IDENTIFIER))
        if self.peek().value == "[":
            node.children.append(self.consume("["))
            node.children.append(self.compile_expression())
            node.children.append(self.consume("]"))
        node.children.append(self.consume("="))
        node.children.append(self.compile_expression())
        node.children.append(self.consume(";"))
        return node

    def compile_if(self) -> NonTerminal:
        node = NonTerminal("ifStatement")
        node.children.append(self.consume("if"))
        node.children.append(self.consume("("))
        node.children.append(self.compile_expression())
        node.children.append(self.consume(")"))
        node.children.append(self.consume("{"))
        node.children.append(self.compile_statements())
        node.children.append(self.consume("}"))
        if self.has_more() and self.peek().value == "else":
            node.children.append(self.consume("else"))
            node.children.append(self.consume("{"))
            node.children.append(self.compile_statements())
            node.children.append(self.consume("}"))
        return node

    def compile_while(self) -> NonTerminal:
        node = NonTerminal("whileStatement")
        node.children.append(self.consume("while"))
        node.children.append(self.consume("("))
        node.children.append(self.compile_expression())
        node.children.append(self.consume(")"))
        node.children.append(self.consume("{"))
        node.children.append(self.compile_statements())
        node.children.append(self.consume("}"))
        return node

    def compile_do(self) -> NonTerminal:
        node = NonTerminal("doStatement")
        node.children.append(self.consume("do"))
        # Subroutine call
        node.children.append(self.consume(expected_type=TokenType.IDENTIFIER))
        if self.peek().value == ".":
            node.children.append(self.consume("."))
            node.children.append(self.consume(expected_type=TokenType.IDENTIFIER))
        node.children.append(self.consume("("))
        node.children.append(self.compile_expression_list())
        node.children.append(self.consume(")"))
        node.children.append(self.consume(";"))
        return node

    def compile_return(self) -> NonTerminal:
        node = NonTerminal("returnStatement")
        node.children.append(self.consume("return"))
        if self.peek().value != ";":
            node.children.append(self.compile_expression())
        node.children.append(self.consume(";"))
        return node

    def compile_expression(self) -> NonTerminal:
        node = NonTerminal("expression")
        node.children.append(self.compile_term())
        ops = ["+", "-", "*", "/", "&", "|", "<", ">", "="]
        while self.has_more() and self.peek().value in ops:
            node.children.append(self.advance())  # op
            node.children.append(self.compile_term())
        return node

    def compile_term(self) -> NonTerminal:
        node = NonTerminal("term")
        peek = self.peek()

        if (
            peek.type == TokenType.INT_CONST
            or peek.type == TokenType.STRING_CONST
            or peek.value in ["true", "false", "null", "this"]
        ):
            node.children.append(self.advance())
        elif peek.value in ["-", "~"]:  # Unary op
            node.children.append(self.advance())
            node.children.append(self.compile_term())
        elif peek.value == "(":
            node.children.append(self.consume("("))
            node.children.append(self.compile_expression())
            node.children.append(self.consume(")"))
        elif peek.type == TokenType.IDENTIFIER:
            # Lookahead to resolve ambiguity
            next_token = self.peek(1)
            if next_token and next_token.value == "[":  # accessing an array
                node.children.append(self.advance())
                node.children.append(self.consume("["))
                node.children.append(self.compile_expression())
                node.children.append(self.consume("]"))
            elif next_token and next_token.value in ["(", "."]:  # subroutine call
                node.children.append(self.advance())
                if next_token.value == ".":
                    node.children.append(self.consume("."))
                    node.children.append(
                        self.consume(expected_type=TokenType.IDENTIFIER)
                    )
                node.children.append(self.consume("("))
                node.children.append(self.compile_expression_list())
                node.children.append(self.consume(")"))
            else:  # Standard variable
                node.children.append(self.advance())
        return node

    def compile_expression_list(self) -> NonTerminal:
        node = NonTerminal("expressionList")
        if self.peek().value != ")":
            node.children.append(self.compile_expression())
            while self.peek().value == ",":
                node.children.append(self.consume(","))
                node.children.append(self.compile_expression())
        return node


# Code Generation - XML Serializer
def escape_xml(char: str) -> str:
    mapping = {"<": "&lt;", ">": "&gt;", '"': "&quot;", "&": "&amp;"}
    return mapping.get(char, char)


def generate_xml(node: Union[NonTerminal, Terminal], indent: int = 0) -> str:
    spaces = "  " * indent
    if isinstance(node, Terminal):
        tag_map = {
            TokenType.KEYWORD: "keyword",
            TokenType.SYMBOL: "symbol",
            TokenType.IDENTIFIER: "identifier",
            TokenType.INT_CONST: "integerConstant",
            TokenType.STRING_CONST: "stringConstant",
        }
        tag = tag_map[node.token.type]
        val = escape_xml(node.token.value)
        return f"{spaces}<{tag}> {val} </{tag}>"
    else:
        # NonTerminal Node
        lines = [f"{spaces}<{node.name}>"]
        for child in node.children:
            lines.append(generate_xml(child, indent + 1))
        lines.append(f"{spaces}</{node.name}>")
        return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        print("Usage: python JackAnalyzer.py <file.jack | directory>")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if input_path.is_dir():
        jack_files = list(input_path.glob("*.jack"))
    else:
        jack_files = [input_path]

    for jack_file in jack_files:
        # read & tokenize
        raw_text = jack_file.read_text()
        tokens = tokenize(raw_text)

        # parsing
        parser = CompilationEngine(tokens)
        ast = parser.compile_class()

        # Generate XML
        xml_output = generate_xml(ast)

        output_file = jack_file.with_name(f"My{jack_file.stem}.xml")
        output_file.write_text(xml_output + "\n")
        print(f"Generated {output_file.name}")


if __name__ == "__main__":
    main()
