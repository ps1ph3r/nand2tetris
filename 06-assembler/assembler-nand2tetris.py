import sys
from pathlib import Path
from dataclasses import dataclass

COMP = {
    "0":   "0101010",
    "1":   "0111111",
    "-1":  "0111010",
    "D":   "0001100",
    "A":   "0110000",
    "!D":  "0001101",
    "!A":  "0110001",
    "-D":  "0001111",
    "-A":  "0110011",
    "D+1": "0011111",
    "A+1": "0110111",
    "D-1": "0001110",
    "A-1": "0110010",
    "D+A": "0000010",
    "D-A": "0010011",
    "A-D": "0000111",
    "D&A": "0000000",
    "D|A": "0010101",


    "M":   "1110000",
    "!M":  "1110001",
    "-M":  "1110011",
    "M+1": "1110111",
    "M-1": "1110010",
    "D+M": "1000010",
    "D-M": "1010011",
    "M-D": "1000111",
    "D&M": "1000000",
    "D|M": "1010101",
}

DEST = {
    "": "000",   # when no dest (just comp;jump)
    "M":  "001",
    "D":  "010",
    "MD": "011",
    "A":  "100",
    "AM": "101",
    "AD": "110",
    "AMD":"111",
}

JUMP = {
    "": "000",   # when no jump
    "JGT": "001",
    "JEQ": "010",
    "JGE": "011",
    "JLT": "100",
    "JNE": "101",
    "JLE": "110",
    "JMP": "111",
}

@dataclass
class AIns:
    value: str

@dataclass
class CIns:
    dest: str
    comp: str
    jump: str

@dataclass
class Label:
    label: str


def to_bin(n: int) -> str:
    return f"{n:016b}"

def parse_line(line: str):
    match line:
        case l if l.startswith("@"):
            return AIns(l[1:])

        case l if l.startswith("(") and l.endswith(")"):
            return Label(l[1:-1])
        
        case _:
            if "=" in line:
                dest, remainder = line.split("=")
            else:
                dest = ""
                remainder = line

            if ";" in remainder:
                comp, jmp = remainder.split(";")
            else:
                comp = remainder
                jmp = ""

            return CIns(dest, comp, jmp)
            

def first_pass(lines):
    symbols = {
        ## Builtin
        "SP": 0,
        "LCL": 1,
        "ARG": 2,
        "THIS": 3,
        "THAT": 4,
        "SCREEN": 16384,
        "KBD": 24576,

        ## Ram Builtin
        **{f"R{i}": i for i in range(16)}
    }

    rom_address = 0

    for instr in lines:
        match instr:
            case Label(label=label):
                symbols[label] = rom_address
            case _:
                rom_address += 1
    return symbols


def second_pass(lines, symbols):
    ram_address = 16
    binary = []

    for instr in lines:
        match instr:
            case AIns(value=value):
                if value.isdigit():
                    addr = int(value)
                else:
                    if value not in symbols:
                        symbols[value] = ram_address
                        ram_address += 1
                    addr = symbols[value]

                binary.append(to_bin(addr))

            case CIns(dest=dest, comp=comp, jump=jump):
               binary.append("111" + COMP[comp] + DEST[dest] + JUMP[jump])

            case Label():
                continue

    return binary

def assemble(input_path, output_path):
    parsed = []
    for l in Path(input_path).read_text().splitlines():
        c = l.split("//")[0].strip()
        if c:
            parsed.append(parse_line(c))

    symbols = first_pass(parsed)

    binary = second_pass(parsed, symbols)
    Path(output_path).write_text("\n".join(binary))


input_path = sys.argv[1]
output_path = str(Path(input_path).with_suffix(".hack"))

assemble(input_path, output_path)
