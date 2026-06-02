import ast
from utils.logger_utils import log_to_file

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
    except SyntaxError: # Catch only parsing errors here
        # Syntax errors are handled by validate_code() separately,
        # but we return empty here to avoid further processing if parsing fails.
        # This ensures we don't try to visit an invalid AST.
        return [] 
    except Exception as e: # Catch other potential errors during parsing
        log_message = f"Error during AST parsing: {str(e)}"
        print(f"[yellow]⚠️ Warning: {log_message}. Skipping blocking code check.[/yellow]")
        log_to_file(log_message, "AST_ERROR")
        return []

    class BlockingVisitor(ast.NodeVisitor):
        """
        AST Visitor that tracks context (functions, classes, main blocks)
        to identify unprotected blocking calls.
        This is a safety mechanism. It protects the developer (or the LLM) from accidentally writing code that works perfectly
        when run as a standalone script but breaks the entire system when the file is imported as a library or component. By
        catching these issues via AST analysis, you avoid having to actually run the code to discover that it hangs the
        system.
        """
        def __init__(self):
            self.in_main_block = False
            self.in_function_or_class = False # Track if inside function/class scope

        def visit_If(self, node):
            is_main_guard = False
            # Check for: if __name__ == "__main__":
            if (isinstance(node.test, ast.Compare) and 
                isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"):
                for comparator in node.test.comparators:
                    # Using ast.Constant for Python 3.8+ compatibility
                    if isinstance(comparator, ast.Constant) and comparator.value == "__main__":
                        is_main_guard = True
                        break

            # Process the body of the if statement if it's the main guard
            if is_main_guard:
                old_main_block_state = self.in_main_block
                self.in_main_block = True
                # Correctly iterate through the list of statements in the body
                for stmt in node.body:
                    self.visit(stmt)
                self.in_main_block = old_main_block_state
                
                # Also visit the orelse part (else/elif) with the old state
                # Correctly iterate through the list of statements in the orelse block
                for stmt in node.orelse:
                    self.visit(stmt)
            else:
                # Visit body and orelse normally if not a main guard
                for stmt in node.body:
                    self.visit(stmt)
                for stmt in node.orelse:
                    self.visit(stmt)

        def visit_FunctionDef(self, node):
            # Code inside functions is generally safe to import
            old_context = self.in_function_or_class
            self.in_function_or_class = True
            self.generic_visit(node) # Use generic_visit for node's children
            self.in_function_or_class = old_context

        def visit_ClassDef(self, node):
            # Code inside classes is generally safe to import
            old_context = self.in_function_or_class
            self.in_function_or_class = True
            self.generic_visit(node) # Use generic_visit for node's children
            self.in_function_or_class = old_context

        def visit_While(self, node):
            # Detect: while True:, while 1:, etc.
            is_infinite = False
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                is_infinite = True
            elif isinstance(node.test, ast.Name) and node.test.id == 'True': # Legacy check
                is_infinite = True
            elif isinstance(node.test, ast.Constant) and node.test.value == 1: # Check for while 1:
                is_infinite = True

            # If it's infinite AND not protected by a main block, warn!
            if is_infinite and not self.in_main_block:
                # Use ast.unparse for a more robust representation of the test condition
                try:
                    condition_str = ast.unparse(node.test)
                except AttributeError: # Fallback for older Python versions if ast.unparse is not available
                    condition_str = "<complex condition>"
                warnings.append(f"Line {node.lineno}: Unprotected infinite 'while' loop detected (condition: {condition_str}). This will hang the app on import.")
            self.generic_visit(node) # Ensure children are visited

        def visit_Call(self, node):
            # Detect: input() calls
            if isinstance(node.func, ast.Name) and node.func.id == 'input':
                # If it's an input call and not protected by a main block, warn!
                if not self.in_main_block:
                    warnings.append(f"Line {node.lineno}: Unprotected 'input()' call detected. This will hang the app on import.")
            self.generic_visit(node) # Ensure children are visited

    visitor = BlockingVisitor()
    try:
        visitor.visit(tree)
    except Exception as e: # Catch runtime errors during AST traversal
        error_msg = f"An unexpected error occurred during AST traversal: {str(e)}"
        print(f"[yellow]⚠️ Warning: {error_msg}. Skipping blocking code check.[/yellow]")
        log_to_file(error_msg, "AST_TRAVERSAL_ERROR")
        # Return empty warnings as we couldn't complete the check
        return [] 
    
    return warnings
