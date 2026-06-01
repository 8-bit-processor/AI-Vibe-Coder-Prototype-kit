import ast
import astunparse
import os

class PatchEngine:
    """
    Surgically replaces specific functions or classes in a file using AST.
    This prevents full-file overwrites and preserves the rest of the code.
    """
    
    @staticmethod
    def replace_node(source_code: str, identifier: str, new_node_code: str) -> str:
        """
        Replaces a node (function or class) in source_code identified by 'identifier' 
        (e.g., 'ClassName.method_name' or 'function_name') with new_node_code.
        """
        tree = ast.parse(source_code)
        new_node_tree = ast.parse(new_node_code.strip())
        
        # Ensure we only have one top-level node in the replacement
        if not new_node_tree.body:
            raise ValueError("Replacement code is empty.")
        
        replacement_node = new_node_tree.body[0]
        
        # Split identifier: "ClassName.method_name" -> ["ClassName", "method_name"]
        parts = identifier.split('.')
        
        class Transformer(ast.NodeTransformer):
            def __init__(self, parts, replacement_node):
                self.parts = parts
                self.replacement_node = replacement_node
                self.found = False

            def visit_FunctionDef(self, node):
                if len(self.parts) == 1 and node.name == self.parts[0]:
                    self.found = True
                    return self.replacement_node
                return self.generic_visit(node)

            def visit_ClassDef(self, node):
                if len(self.parts) >= 1 and node.name == self.parts[0]:
                    if len(self.parts) == 1:
                        self.found = True
                        return self.replacement_node
                    else:
                        # Continue searching inside the class
                        inner_transformer = Transformer(self.parts[1:], self.replacement_node)
                        node.body = [inner_transformer.visit(item) for item in node.body]
                        if inner_transformer.found:
                            self.found = True
                        return node
                return self.generic_visit(node)

        transformer = Transformer(parts, replacement_node)
        new_tree = transformer.visit(tree)
        
        if not transformer.found:
            raise ValueError(f"Identifier '{identifier}' not found in source code.")
            
        return astunparse.unparse(new_tree)

    def apply_patch(self, file_path: str, identifier: str, patch_code: str) -> bool:
        """
        Reads a file, applies a patch to the specific identifier, and writes it back.
        """
        if not os.path.exists(file_path):
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            updated_code = self.replace_node(source, identifier, patch_code)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_code)
            return True
        except Exception as e:
            print(f"Patch error: {e}")
            return False
