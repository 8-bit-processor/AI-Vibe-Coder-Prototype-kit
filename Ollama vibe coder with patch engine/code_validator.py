import ast

def validate_code(code: str) -> tuple[bool, str]:
    """
    Validates Python code syntax and basic structure using the ast module.
    Returns (is_valid, error_message).
    
    This is used as a safety gate before any code is saved to disk.
    """
    try:
        ast.parse(code)
        return True, "Valid syntax"
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}, column {e.offset}: {e.msg}"
    except Exception as e:
        return False, f"Unexpected validation error: {str(e)}"

def check_blocking_code(code: str) -> list[str]:
    """
    System Guard: Analyzes code for blocking constructs (infinite loops, input())
    that are not protected by if __name__ == "__main__":
    
    This prevents 'deadlock' bugs when generated code is imported as a module.
    Returns a list of human-readable warnings.
    """
    warnings = []
    try:
        tree = ast.parse(code)
    except:
        return [] # Syntax errors are handled by validate_code() separately

    class BlockingVisitor(ast.NodeVisitor):
        """
        AST Visitor that tracks context (functions, classes, main blocks)
        to identify unprotected blocking calls.
        """
        def __init__(self):
            self.in_main_block = False
            self.in_function_or_class = False

        def visit_If(self, node):
            # Check for: if __name__ == "__main__":
            is_main = False
            if isinstance(node.test, ast.Compare):
                # Look for '__name__' on the left side
                if isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__":
                    for op_val in node.test.comparators:
                        # Look for '"__main__"' on the right side
                        if isinstance(op_val, (ast.Constant, ast.Str)):
                            val = op_val.value if isinstance(op_val, ast.Constant) else op_val.s
                            if val == "__main__":
                                is_main = True
            
            # Enter the block and track that we are now 'safe' inside a main guard
            old_main = self.in_main_block
            if is_main: self.in_main_block = True
            self.generic_visit(node)
            self.in_main_block = old_main

        def visit_FunctionDef(self, node):
            # Code inside functions is safe to import
            old_context = self.in_function_or_class
            self.in_function_or_class = True
            self.generic_visit(node)
            self.in_function_or_class = old_context

        def visit_ClassDef(self, node):
            # Code inside classes is safe to import
            old_context = self.in_function_or_class
            self.in_function_or_class = True
            self.generic_visit(node)
            self.in_function_or_class = old_context

        def visit_While(self, node):
            # Detect: while True:, while 1:, etc.
            is_infinite = False
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                is_infinite = True
            elif isinstance(node.test, ast.Name) and node.test.id == 'True':
                is_infinite = True
            elif isinstance(node.test, ast.Constant) and node.test.value == 1:
                is_infinite = True

            # If it's infinite AND at the top level (not in function/main block), warn!
            if is_infinite and not self.in_main_block and not self.in_function_or_class:
                warnings.append(f"Line {node.lineno}: Unprotected infinite 'while' loop detected. This will freeze the app on import.")
            self.generic_visit(node)

        def visit_Call(self, node):
            # Detect: input() calls at the top level
            if isinstance(node.func, ast.Name) and node.func.id == 'input':
                if not self.in_main_block and not self.in_function_or_class:
                    warnings.append(f"Line {node.lineno}: Unprotected 'input()' call detected. This will hang the app on import.")
            self.generic_visit(node)

    visitor = BlockingVisitor()
    visitor.visit(tree)
    return warnings
