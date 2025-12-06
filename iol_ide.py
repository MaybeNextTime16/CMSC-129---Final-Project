import sys
import re
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPlainTextEdit, QFileDialog, QTextEdit, QTableWidget, QTableWidgetItem,
    QMenuBar, QMessageBox
)
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt


# ============================================================
# LEXICAL ANALYZER (IOL)
# ============================================================
class IOLLexer:
    TOKEN_REGEX = [
        ("IOL", r"\bIOL\b"),
        ("LOI", r"\bLOI\b"),
        ("TYPE", r"\b(INT|STR)\b"),
        ("BEG", r"\bBEG\b"),
        ("INTO", r"\bINTO\b"),
        ("IS", r"\bIS\b"),
        ("PRINT", r"\bPRINT\b"),
        ("NEWLN", r"\bNEWLN\b"),
        ("ADD", r"\bADD\b"),
        ("SUB", r"\bSUB\b"),
        ("MULT", r"\bMULT\b"),
        ("DIV", r"\bDIV\b"),
        ("MOD", r"\bMOD\b"),

        ("INTEGER", r"\b\d+\b"),
        ("IDENT", r"\b[a-zA-Z][a-zA-Z0-9]*\b"),
    ]

    def tokenize(self, code):
        tokens = []
        errors = []

        pos = 0
        while pos < len(code):
            if code[pos].isspace():
                pos += 1
                continue

            match_found = False
            for tok_type, pattern in self.TOKEN_REGEX:
                regex = re.compile(pattern)
                match = regex.match(code, pos)
                if match:
                    tokens.append((tok_type, match.group()))
                    pos = match.end()
                    match_found = True
                    break

            if not match_found:
                errors.append(f"Unknown token at position {pos}: {code[pos]}")
                pos += 1

        return tokens, errors


# ============================================================
# PARSER + STATIC SEMANTICS
# ============================================================
class IOLParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0
        self.variables = {}  # varname -> type (INT/STR)

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else ("EOF", "")

    def advance(self):
        self.index += 1

    def parse(self):
        errors = []

        # Must start with IOL
        if self.peek()[0] != "IOL":
            errors.append("Program must start with 'IOL'")
            return errors
        self.advance()

        # Statements until LOI
        while self.peek()[0] != "LOI":
            tok, val = self.peek()

            if tok == "TYPE":
                # variable declaration
                dtype = val
                self.advance()

                tok2, varname = self.peek()
                if tok2 != "IDENT":
                    errors.append("Expected variable name")
                else:
                    self.variables[varname] = dtype
                self.advance()

                # optional initialization
                if self.peek()[0] == "IS":
                    self.advance()
                    expr_tok, expr_val = self.peek()
                    if dtype == "INT" and expr_tok != "INTEGER":
                        errors.append(f"Variable {varname} must be initialized with INTEGER")
                    self.advance()

            elif tok == "INTO":
                self.advance()
                tok2, varname = self.peek()
                if varname not in self.variables:
                    errors.append(f"Variable {varname} not declared")
                self.advance()
                if self.peek()[0] != "IS":
                    errors.append("Expected IS")
                self.advance()
                # Skipping full expression parsing for now
                self.advance()

            elif tok == "PRINT":
                self.advance()
                self.advance()

            elif tok == "BEG":
                self.advance()
                self.advance()

            else:
                errors.append(f"Unexpected token: {val}")
                self.advance()

            if self.peek()[0] == "EOF":
                errors.append("Expected LOI at end of program")
                break

        return errors


# ============================================================
# EXECUTION ENGINE
# ============================================================
class IOLExecutor:
    def __init__(self):
        self.vars = {}

    def execute(self, code, console):

        # VERY BASIC placeholder runtime
        console.appendPlainText("Executing program...")
        console.appendPlainText("Runtime engine not fully implemented.")
        console.appendPlainText("---- END ----")


# ============================================================
# IOL IDE MAIN WINDOW
# ============================================================
class IOL_IDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IOL IDE - Integer Oriented Language")
        self.resize(1200, 800)

        # File handling
        self.current_file = None

        # ======== MAIN UI LAYOUT ========
        central = QWidget()
        layout = QHBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        # -------- Left side: editor + console --------
        left_panel = QVBoxLayout()

        # Code Editor
        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet("background-color: #111; color: #0f0; font-size: 14px;")
        left_panel.addWidget(self.editor)

        # Console
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #000; color: #0ff; font-size: 14px;")
        left_panel.addWidget(self.console)

        layout.addLayout(left_panel, 3)

        # -------- Right side: variable table --------
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Variable", "Type"])
        self.table.setStyleSheet("background-color: #222; color: white; font-size: 14px;")
        layout.addWidget(self.table, 1)

        # ======== MENU BAR ========
        self.make_menu_bar()

    # ============================================================
    # MENU BAR
    # ============================================================
    def make_menu_bar(self):
        menu = self.menuBar()
        menu.setStyleSheet("background-color: #333; color: white;")

        file_menu = menu.addMenu("File")
        compile_menu = menu.addMenu("Compile")
        run_menu = menu.addMenu("Execute")

        # File actions
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

        # Compile actions
        act_compile = QAction("Compile Code", self)
        act_compile.setShortcut(QKeySequence("Ctrl+Shift+C"))
        act_compile.triggered.connect(self.compile_code)

        act_tokens = QAction("Show Tokenized Code", self)
        act_tokens.setShortcut(QKeySequence("Ctrl+T"))
        act_tokens.triggered.connect(self.show_tokens)

        compile_menu.addActions([act_compile, act_tokens])

        # Execute
        act_run = QAction("Execute Code", self)
        act_run.setShortcut(QKeySequence("Ctrl+R"))
        act_run.triggered.connect(self.run_code)

        run_menu.addAction(act_run)

    # ============================================================
    # FILE HANDLING
    # ============================================================
    def new_file(self):
        self.editor.clear()
        self.current_file = None
        self.console.appendPlainText("New file created.")

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "IOL Files (*.iol)")
        if path:
            self.current_file = path
            with open(path, "r") as f:
                self.editor.setPlainText(f.read())
            self.console.appendPlainText(f"Opened file: {path}")

    def save_file(self):
        if self.current_file is None:
            return self.save_file_as()
        with open(self.current_file, "w") as f:
            f.write(self.editor.toPlainText())
        self.console.appendPlainText("File saved.")

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "IOL Files (*.iol)")
        if path:
            self.current_file = path
            self.save_file()

    # ============================================================
    # COMPILATION
    # ============================================================
    def compile_code(self):
        code = self.editor.toPlainText()

        lexer = IOLLexer()
        tokens, lex_errors = lexer.tokenize(code)

        parser = IOLParser(tokens)
        parse_errors = parser.parse()

        self.console.appendPlainText("=== COMPILATION ===")
        if lex_errors:
            self.console.appendPlainText("\n".join(lex_errors))
        if parse_errors:
            self.console.appendPlainText("\n".join(parse_errors))

        if not lex_errors and not parse_errors:
            self.console.appendPlainText("Compilation successful!")

            # Update variable table
            self.table.setRowCount(0)
            for var, dtype in parser.variables.items():
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(var))
                self.table.setItem(r, 1, QTableWidgetItem(dtype))

    def show_tokens(self):
        code = self.editor.toPlainText()
        lexer = IOLLexer()
        tokens, errors = lexer.tokenize(code)

        self.console.appendPlainText("=== TOKENS ===")
        for t in tokens:
            self.console.appendPlainText(str(t))

        if errors:
            self.console.appendPlainText("\n".join(errors))

    # ============================================================
    # EXECUTION
    # ============================================================
    def run_code(self):
        executor = IOLExecutor()
        executor.execute(self.editor.toPlainText(), self.console)


# ============================================================
# MAIN APP LAUNCHER
# ============================================================
app = QApplication(sys.argv)
window = IOL_IDE()
window.show()
sys.exit(app.exec())
