from pydantic import Field

from oxygent.oxy import FunctionHub

math_tools = FunctionHub(name="math_tools")

@math_tools.tool(description="A tool that can calculate the value of pi.")
def calc_pi(prec: int = Field(description="how many decimal places")) -> float:
    import math
    from decimal import Decimal, getcontext

    getcontext().prec = prec
    x = 0
    for k in range(int(prec / 8) + 1):
        a = 2 * Decimal.sqrt(Decimal(2)) / 9801
        b = math.factorial(4 * k) * (1103 + 26390 * k)
        c = pow(math.factorial(k), 4) * pow(396, 4 * k)
        x = x + a * b / c
    return 1 / x

@math_tools.tool(description="A tool that applies a binary operation to corresponding elements of two lists.")
def list_operation(
    list1: list = Field(description="The first list"),
    list2: list = Field(description="The second list"),
    operation: str = Field(description="The operation to perform: 'add', 'subtract', 'multiply', 'divide', 'power', 'mod'")
) -> list:
    """
    Apply a binary operation element-wise between two lists.
    
    Args:
        list1: The first list
        list2: The second list  
        operation: The operation to perform ('add', 'subtract', 'multiply', 'divide', 'power', 'mod')
        
    Returns:
        A new list containing the results of the operation
        
    Raises:
        ValueError: If the lists have different lengths or operation is invalid
    """
    import operator
    if len(list1) != len(list2):
        raise ValueError(f"Lists must have the same length. Got {len(list1)} and {len(list2)}")
    
    # 操作符映射
    operations = {
        'add': operator.add,
        'subtract': operator.sub,
        'multiply': operator.mul,
        'divide': operator.truediv,
        'power': operator.pow,
        'mod': operator.mod
    }
    
    if operation not in operations:
        raise ValueError(f"Invalid operation '{operation}'. Supported operations: {list(operations.keys())}")
    
    op_func = operations[operation]
    
    try:
        return [op_func(a, b) for a, b in zip(list1, list2)]
    except ZeroDivisionError:
        raise ValueError("Division by zero encountered in the operation")
    except Exception as e:
        raise ValueError(f"Error performing {operation}: {str(e)}")
    

@math_tools.tool(description="A tool that evaluates mathematical expressions and returns the expression with its result.")
def calculate_expression(
    expression: str = Field(description="Mathematical expression to evaluate (e.g., '5+6', '10*3-2', '(4+5)*2')")
) -> str:
    """
    Evaluate a mathematical expression and return it with the result.
    Args:
        expression: Mathematical expression string to evaluate
    Returns:
        A string in the format "expression=result" (e.g., "5+6=11")
    Raises:
        ValueError: If the expression is invalid or contains unsafe operations
    """
    import ast
    import operator
    
    # Define allowed operators for safety
    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    
    def safe_eval(node):
        """Safely evaluate an AST node."""
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value
        elif isinstance(node, ast.Num):  # Python < 3.8
            return node.n
        elif isinstance(node, ast.BinOp):
            left = safe_eval(node.left)
            right = safe_eval(node.right)
            op = allowed_operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operation: {type(node.op).__name__}")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = safe_eval(node.operand)
            op = allowed_operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operation: {type(node.op).__name__}")
            return op(operand)
        elif isinstance(node, ast.Expression):
            return safe_eval(node.body)
        else:
            raise ValueError(f"Unsupported AST node type: {type(node).__name__}")
    
    try:
        # Remove whitespace and validate the expression
        clean_expression = expression.strip()
        if not clean_expression:
            raise ValueError("Empty expression")
        
        # Parse the expression into an AST
        tree = ast.parse(clean_expression, mode='eval')
        
        # Evaluate the expression safely
        result = safe_eval(tree)
        
        # Format the result appropriately
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        
        return f"{clean_expression}={result}"
        
    except SyntaxError:
        raise ValueError(f"Invalid mathematical expression: {expression}")
    except ZeroDivisionError:
        raise ValueError(f"Division by zero in expression: {expression}")
    except Exception as e:
        raise ValueError(f"Error evaluating expression '{expression}': {str(e)}")