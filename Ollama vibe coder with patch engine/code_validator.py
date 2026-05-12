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
            is_main_guard = False
            # Check for: if __name__ == "__main__":
            if (isinstance(node.test, ast.Compare) and 
                isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"):
                for comparator in node.test.comparators:
                    if isinstance(comparator, ast.Constant) and comparator.value == "__main__":
                        is_main_guard = True
                        break

            # Process the body of the if statement
            if is_main_guard:
                old_main_block_state = self.in_main_block
                self.in_main_block = True
                self.generic_visit(node.body) # Only visit the body with in_main_block = True
                self.in_main_block = old_main_block_state
                
                # Also visit the orelse part (else/elif) with the old state
                self.generic_visit(node.orelse) 
            else:
                self.generic_visit(node) # Visit as normal if not a main guard

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

            # If it's infinite AND not protected by a main block, warn!
            if is_infinite and not self.in_main_block:
                warnings.append(f"Line {node.lineno}: Unprotected infinite 'while' loop detected (condition: {ast.unparse(node.test)}). This will freeze the app on import.")
            self.generic_visit(node)

        def visit_Call(self, node):
            # Detect: input() calls
            if isinstance(node.func, ast.Name) and node.func.id == 'input':
                # If it's an input call and not protected by a main block, warn!
                if not self.in_main_block:
                    warnings.append(f"Line {node.lineno}: Unprotected 'input()' call detected. This will hang the app on import.")
            self.generic_visit(node)

    visitor = BlockingVisitor()
    visitor.visit(tree)
    return warnings
