import sys
import re
from collections import namedtuple
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QFileDialog, QTextEdit, QTableWidget, QTableWidgetItem,
    QAction, QMessageBox, QInputDialog
)
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt

# Token structure
Token = namedtuple('Token', ['type', 'lexeme', 'line'])

KEYWORDS = {
    'IOL','LOI','INT','STR','BEG','INTO','IS','PRINT','NEWLN','ADD','SUB','MULT','DIV','MOD'
}

ARITH_OPS = {'ADD','SUB','MULT','DIV','MOD'}

# =========================
# LEXICAL ANALYZER
# =========================
class IOLLexer:
    def __init__(self):
        # regex for integer literal and identifier
        self.re_int = re.compile(r'^\d+$')
        self.re_ident = re.compile(r'^[A-Za-z][A-Za-z0-9]*$')

    def tokenize(self, code):
        tokens = []
        errors = []
        lines = code.splitlines()
        for lineno, line in enumerate(lines, start=1):
            # split by whitespace; language uses spaces as delimiter
            parts = line.strip().split()
            for part in parts:
                if part in KEYWORDS:
                    tokens.append(Token(part, part, lineno))
                elif self.re_int.match(part):
                    tokens.append(Token('INT_LIT', part, lineno))
                elif self.re_ident.match(part):
                    tokens.append(Token('IDENT', part, lineno))
                else:
                    errors.append(f"ERR_LEX: Unknown lexeme '{part}' at line {lineno}")
                    tokens.append(Token('ERR_LEX', part, lineno))
        # also add EOF marker
        tokens.append(Token('EOF','', lineno if lines else 1))
        return tokens, errors

    def tokens_to_tkn_stream(self, tokens):
        # produce stream where lexemes replaced by token names, preserve lines
        out_lines = []
        current_line = []
        last_line = tokens[0].line if tokens else 1
        for t in tokens:
            if t.type == 'EOF':
                if current_line:
                    out_lines.append(' '.join(tok for tok in current_line))
                break
            if t.line != last_line:
                out_lines.append(' '.join(current_line))
                current_line = [t.type]
                last_line = t.line
            else:
                current_line.append(t.type)
        return '\n'.join(out_lines)

# =========================
# PARSER / STATIC SEMANTICS
# =========================
class ParseError(Exception):
    pass

class ASTNode:
    pass

class IntLiteral(ASTNode):
    def __init__(self, value):
        self.value = int(value)

class VarRef(ASTNode):
    def __init__(self, name, line):
        self.name = name
        self.line = line

class BinOp(ASTNode):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

class Stmt(ASTNode):
    pass

class Decl(Stmt):
    def __init__(self, dtype, name, init_expr, line):
        self.dtype = dtype
        self.name = name
        self.init_expr = init_expr
        self.line = line

class Assign(Stmt):
    def __init__(self, name, expr, line):
        self.name = name
        self.expr = expr
        self.line = line

class BegInput(Stmt):
    def __init__(self, name, line):
        self.name = name
        self.line = line

class PrintStmt(Stmt):
    def __init__(self, expr, line):
        self.expr = expr
        self.line = line

class NewlnStmt(Stmt):
    def __init__(self, line):
        self.line = line

class IOLParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0
        self.errors = []
        self.symbols = {}  # name -> {'type': 'INT'/'STR', 'line':n}
        self.statements = []

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else Token('EOF','',0)

    def advance(self):
        self.i += 1

    def expect(self, ttype):
        tok = self.peek()
        if tok.type != ttype:
            raise ParseError(f"Expected {ttype} at line {tok.line} but found '{tok.lexeme}'")
        self.advance()
        return tok

    def parse(self):
        try:
            # find first non-empty token and expect IOL
            while self.peek().type == 'ERR_LEX':
                self.errors.append(f"{self.peek().lexeme} at line {self.peek().line} is invalid lexeme")
                self.advance()
            if self.peek().type != 'IOL':
                self.errors.append("Program must start with 'IOL'")
                return self.errors
            self.advance()

            # parse statements until LOI
            while self.peek().type != 'LOI' and self.peek().type != 'EOF':
                tok = self.peek()
                if tok.type in ('INT','STR'):
                    dtype = tok.type
                    line = tok.line
                    self.advance()
                    if self.peek().type != 'IDENT':
                        self.errors.append(f"Expected identifier after {dtype} at line {line}")
                        # try to continue
                        while self.peek().type not in ('INT','STR','BEG','INTO','PRINT','NEWLN','LOI','EOF'):
                            self.advance()
                        continue
                    name = self.peek().lexeme
                    name_line = self.peek().line
                    if name in self.symbols:
                        self.errors.append(f"Variable '{name}' redeclared at line {name_line}")
                    self.advance()
                    init_expr = None
                    if self.peek().type == 'IS':
                        self.advance()
                        # parse expression or literal for init
                        init_expr = self.parse_expr()
                        # check type
                        if dtype == 'INT' and isinstance(init_expr, IntLiteral):
                            pass
                        elif dtype == 'INT' and isinstance(init_expr, VarRef):
                            # variable ref must be INT
                            if init_expr.name not in self.symbols:
                                self.errors.append(f"Undeclared variable '{init_expr.name}' used in initialization at line {init_expr.line}")
                        elif dtype == 'STR':
                            # initialization for STR not allowed unless from BEG? spec says STR has no literal; disallow literal init
                            self.errors.append(f"String variable '{name}' cannot be initialized with a literal at line {name_line}")
                    self.symbols[name] = {'type': dtype, 'line': name_line}
                    self.statements.append(Decl(dtype, name, init_expr, line))

                elif tok.type == 'INTO':
                    line = tok.line
                    self.advance()
                    if self.peek().type != 'IDENT':
                        self.errors.append(f"Expected identifier after INTO at line {line}")
                        continue
                    name = self.peek().lexeme
                    if name not in self.symbols:
                        self.errors.append(f"Variable '{name}' not declared at line {self.peek().line}")
                    self.advance()
                    if self.peek().type != 'IS':
                        self.errors.append(f"Expected IS after variable in INTO at line {line}")
                    else:
                        self.advance()
                        expr = self.parse_expr()
                        # type check: expr must be INT for INT var
                        if name in self.symbols and self.symbols[name]['type'] == 'INT':
                            if not self.expr_is_int(expr):
                                self.errors.append(f"Type error: cannot assign non-integer to INT variable '{name}' at line {line}")
                        else:
                            # STR assignment from expr not allowed (only via BEG)
                            self.errors.append(f"Type error: cannot assign to STR variable '{name}' via INTO at line {line}")
                        self.statements.append(Assign(name, expr, line))

                elif tok.type == 'BEG':
                    line = tok.line
                    self.advance()
                    if self.peek().type != 'IDENT':
                        self.errors.append(f"Expected identifier after BEG at line {line}")
                        continue
                    name = self.peek().lexeme
                    if name not in self.symbols:
                        self.errors.append(f"Variable '{name}' not declared at line {self.peek().line}")
                    self.advance()
                    self.statements.append(BegInput(name, line))

                elif tok.type == 'PRINT':
                    line = tok.line
                    self.advance()
                    if self.peek().type == 'NEWLN':
                        # allow PRINT NEWLN ??? but spec uses separate NEWLN token — handle separately
                        self.errors.append(f"Unexpected NEWLN after PRINT at line {line}")
                    expr = self.parse_expr()
                    # expr can be literal, var, or numeric expr
                    self.statements.append(PrintStmt(expr, line))

                elif tok.type == 'NEWLN':
                    line = tok.line
                    self.advance()
                    self.statements.append(NewlnStmt(line))

                else:
                    # unexpected token
                    self.errors.append(f"Unexpected token '{tok.lexeme}' at line {tok.line}")
                    self.advance()

            # after loop expect LOI
            if self.peek().type != 'LOI':
                self.errors.append("Expected LOI at end of program")
            else:
                self.advance()

        except ParseError as pe:
            self.errors.append(str(pe))

        return self.errors

    def parse_expr(self):
        tok = self.peek()
        if tok.type in ARITH_OPS:
            op = tok.type
            self.advance()
            left = self.parse_expr()
            right = self.parse_expr()
            return BinOp(op, left, right)
        elif tok.type == 'INT_LIT':
            self.advance()
            return IntLiteral(tok.lexeme)
        elif tok.type == 'IDENT':
            self.advance()
            return VarRef(tok.lexeme, tok.line)
        else:
            # unexpected token in expression
            # consume and return a dummy literal 0 to continue parsing
            self.errors.append(f"Invalid expression token '{tok.lexeme}' at line {tok.line}")
            self.advance()
            return IntLiteral('0')

    def expr_is_int(self, expr):
        if isinstance(expr, IntLiteral):
            return True
        if isinstance(expr, VarRef):
            if expr.name in self.symbols and self.symbols[expr.name]['type'] == 'INT':
                return True
            else:
                return False
        if isinstance(expr, BinOp):
            return self.expr_is_int(expr.left) and self.expr_is_int(expr.right)
        return False

# =========================
# EXECUTION ENGINE
# =========================
class IOLExecutor:
    def __init__(self, statements, symbols, console, table_widget):
        self.statements = statements
        # prepare runtime variables: name -> {'type':, 'value':}
        self.vars = {name: {'type':info['type'], 'value': 0 if info['type']=='INT' else ''} for name,info in symbols.items()}
        self.console = console
        self.table = table_widget

    def update_table(self):
        self.table.setRowCount(0)
        for name, info in self.vars.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r,0, QTableWidgetItem(name))
            self.table.setItem(r,1, QTableWidgetItem(info['type']))
            self.table.setItem(r,2, QTableWidgetItem(str(info['value'])))

    def run(self):
        # ensure table has 3 columns: var, type, value
        if self.table.columnCount() < 3:
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["Variable","Type","Value"])
        try:
            for stmt in self.statements:
                if isinstance(stmt, Decl):
                    if stmt.init_expr:
                        val = self.eval_expr(stmt.init_expr)
                        if self.vars[stmt.name]['type'] == 'INT':
                            self.vars[stmt.name]['value'] = val
                elif isinstance(stmt, Assign):
                    val = self.eval_expr(stmt.expr)
                    # assign only to INT per parser
                    self.vars[stmt.name]['value'] = val
                elif isinstance(stmt, BegInput):
                    vtype = self.vars[stmt.name]['type']
                    if vtype == 'INT':
                        text, ok = QInputDialog.getText(None, "Input", f"Input for {stmt.name}:")
                        if not ok:
                            raise RuntimeError(f"Input cancelled for {stmt.name} at line {stmt.line}")
                        # validate integer
                        try:
                            val = int(text)
                        except Exception:
                            raise RuntimeError(f"Runtime type error: expected integer for {stmt.name} at line {stmt.line}")
                        self.vars[stmt.name]['value'] = val
                    else:
                        text, ok = QInputDialog.getText(None, "Input", f"Input for {stmt.name}:")
                        if not ok:
                            raise RuntimeError(f"Input cancelled for {stmt.name} at line {stmt.line}")
                        self.vars[stmt.name]['value'] = text
                elif isinstance(stmt, PrintStmt):
                    val = self.eval_expr(stmt.expr)
                    self.console.appendPlainText(str(val))
                elif isinstance(stmt, NewlnStmt):
                    self.console.appendPlainText("")
                else:
                    # unknown stmt
                    pass
                self.update_table()
            self.console.appendPlainText("\nProgram terminated successfully...")
        except RuntimeError as re:
            self.console.appendPlainText(f"Runtime Error: {str(re)}")

    def eval_expr(self, expr):
        if isinstance(expr, IntLiteral):
            return expr.value
        if isinstance(expr, VarRef):
            if expr.name not in self.vars:
                raise RuntimeError(f"Undeclared variable '{expr.name}' at line {expr.line}")
            val = self.vars[expr.name]['value']
            if self.vars[expr.name]['type'] != 'INT':
                raise RuntimeError(f"Type error: variable '{expr.name}' is not integer at line {expr.line}")
            return int(val)
        if isinstance(expr, BinOp):
            l = self.eval_expr(expr.left)
            r = self.eval_expr(expr.right)
            if expr.op == 'ADD':
                return l + r
            if expr.op == 'SUB':
                return l - r
            if expr.op == 'MULT':
                return l * r
            if expr.op == 'DIV':
                if r == 0:
                    raise RuntimeError('Division by zero')
                return l // r
            if expr.op == 'MOD':
                return l % r
        raise RuntimeError('Invalid expression during evaluation')

# =========================
# IOL IDE MAIN WINDOW
# =========================
class IOL_IDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IOL IDE - Integer Oriented Language")
        self.resize(1200, 800)

        self.current_file = None

        central = QWidget()
        layout = QHBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        left_panel = QVBoxLayout()
        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet("background-color: #111; color: #0f0; font-size: 14px;")
        left_panel.addWidget(self.editor)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #000; color: #0ff; font-size: 14px;")
        left_panel.addWidget(self.console)

        layout.addLayout(left_panel, 3)

        # variable table with 3 columns
        self.table = QTableWidget(0,3)
        self.table.setHorizontalHeaderLabels(["Variable","Type","Value"])
        self.table.setStyleSheet("background-color: #222; color: white; font-size: 14px;")
        layout.addWidget(self.table,1)

        self.make_menu_bar()

    def make_menu_bar(self):
        menu = self.menuBar()
        menu.setStyleSheet("background-color: #333; color: white;")

        file_menu = menu.addMenu("File")
        compile_menu = menu.addMenu("Compile")
        run_menu = menu.addMenu("Execute")

        act_new = QAction("New", self)
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.triggered.connect(self.new_file)

        act_open = QAction("Open", self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self.open_file)

        act_save = QAction("Save", self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self.save_file)

        act_save_as = QAction("Save As", self)
        act_save_as.triggered.connect(self.save_file_as)

        file_menu.addActions([act_new, act_open, act_save, act_save_as])

        act_compile = QAction("Compile Code", self)
        act_compile.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_compile.triggered.connect(self.compile_code)

        act_tokens = QAction("Show Tokenized Code", self)
        act_tokens.setShortcut(QKeySequence("Ctrl+T"))
        act_tokens.triggered.connect(self.show_tokens)

        compile_menu.addActions([act_compile, act_tokens])

        act_run = QAction("Execute Code", self)
        act_run.setShortcut(QKeySequence("Ctrl+R"))
        act_run.triggered.connect(self.run_code)

        run_menu.addAction(act_run)

    # File handling
    def new_file(self):
        self.editor.clear()
        self.current_file = None
        self.console.appendPlainText("New file created.")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "IOL Files (*.iol)")
        if path:
            self.current_file = path
            with open(path,'r') as f:
                self.editor.setPlainText(f.read())
            self.console.appendPlainText(f"Opened file: {path}")

    def save_file(self):
        if self.current_file is None:
            return self.save_file_as()
        with open(self.current_file,'w') as f:
            f.write(self.editor.toPlainText())
        self.console.appendPlainText("File saved.")

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "IOL Files (*.iol)")
        if path:
            self.current_file = path
            self.save_file()

    # Compilation
    def compile_code(self):
        code = self.editor.toPlainText()
        lexer = IOLLexer()
        tokens, lex_errors = lexer.tokenize(code)

        # write token stream to .tkn file if compiled successfully
        parser = IOLParser(tokens)
        parse_errors = parser.parse()

        self.console.appendPlainText("=== COMPILATION ===")
        if lex_errors:
            for e in lex_errors:
                self.console.appendPlainText(e)
        if parse_errors:
            for e in parse_errors:
                self.console.appendPlainText(e)

        if not lex_errors and not parse_errors:
            self.console.appendPlainText("Compilation successful!")
            # write token stream file
            tkn_stream = lexer.tokens_to_tkn_stream(tokens)
            # if current file exists, create .tkn alongside
            if self.current_file:
                tkn_path = self.current_file.rsplit('.',1)[0] + '.tkn'
            else:
                tkn_path, _ = QFileDialog.getSaveFileName(self, "Save Token Stream", "tokens.tkn", "Token files (*.tkn)")
            if tkn_path:
                with open(tkn_path,'w') as f:
                    f.write(tkn_stream)
                self.console.appendPlainText(f"Token stream written to {tkn_path}")

            # update variable table
            self.table.setRowCount(0)
            # ensure 3 columns
            if self.table.columnCount() < 3:
                self.table.setColumnCount(3)
                self.table.setHorizontalHeaderLabels(["Variable","Type","Value"])
            for var, info in parser.symbols.items():
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r,0, QTableWidgetItem(var))
                self.table.setItem(r,1, QTableWidgetItem(info['type']))
                self.table.setItem(r,2, QTableWidgetItem(''))

            # store last compiled state
            self.last_compiled = {'statements': parser.statements, 'symbols': parser.symbols}
        else:
            self.console.appendPlainText("Compilation failed. Fix errors and try again.")
            self.last_compiled = None

    def show_tokens(self):
        code = self.editor.toPlainText()
        lexer = IOLLexer()
        tokens, errors = lexer.tokenize(code)
        self.console.appendPlainText("=== TOKENS ===")
        for t in tokens:
            if t.type == 'EOF':
                continue
            self.console.appendPlainText(f"{t.type}\t{t.lexeme}\t(line {t.line})")
        if errors:
            for e in errors:
                self.console.appendPlainText(e)

    def run_code(self):
        # ensure compiled
        if not hasattr(self, 'last_compiled') or not self.last_compiled:
            self.console.appendPlainText("Code must be compiled successfully before execution.")
            return
        self.console.appendPlainText("=== PROGRAM EXECUTION ===")
        executor = IOLExecutor(self.last_compiled['statements'], self.last_compiled['symbols'], self.console, self.table)
        executor.run()

# Main
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = IOL_IDE()
    window.show()
    sys.exit(app.exec())
