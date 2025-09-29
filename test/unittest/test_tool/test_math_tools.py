import pytest

from oxygent.preset_tools.math_tools import calc_pi, list_operation, calculate_expression

@pytest.mark.asyncio
async def test_calculate_expression_operations():
    """Test basic arithmetic operations."""
    # Test addition
    result = await calculate_expression("5+3")
    assert result == "5+3=8"
    
    # Test subtraction
    result = await calculate_expression("10-4")
    assert result == "10-4=6"
    
    # Test multiplication
    result = await calculate_expression("6*7")
    assert result == "6*7=42"
    
    # Test division
    result = await calculate_expression("15/3")
    assert result == "15/3=5"

    # Test parentheses
    result = await calculate_expression("(5+3)*2")
    assert result == "(5+3)*2=16"
    
    # Test multiple operations
    result = await calculate_expression("10+5*2")
    assert result == "10+5*2=20"
    
    # Test floating point operations
    result = await calculate_expression("7.5+2.5")
    assert result == "7.5+2.5=10"

    # Test calculate_expression with whitespace
    result = await calculate_expression("  5 + 3  ")
    assert result == "5 + 3=8"

    # Test negative numbers in calculate_expression
    result = await calculate_expression("-5+3")
    assert result == "-5+3=-2"


@pytest.mark.asyncio
async def test_calculate_expression_error_cases():
    """Test error handling for invalid expressions."""
    # Test empty expression
    with pytest.raises(ValueError, match="Empty expression"):
        await calculate_expression("")
    
    # Test invalid syntax
    with pytest.raises(ValueError, match="Invalid mathematical expression"):
        await calculate_expression("5..3")
    
    # Test division by zero
    with pytest.raises(ValueError, match="Division by zero"):
        await calculate_expression("5/0")

@pytest.mark.asyncio
async def test_list_operation_basic_operations():
    """Test basic list operations."""
    # Test addition
    result = await list_operation([1, 2, 3], [4, 5, 6], "add")
    assert result == [5, 7, 9]
    
    # Test subtraction
    result = await list_operation([10, 8, 6], [3, 2, 1], "subtract")
    assert result == [7, 6, 5]
    
    # Test multiplication
    result = await list_operation([2, 3, 4], [5, 6, 7], "multiply")
    assert result == [10, 18, 28]
    
    # Test division
    result = await list_operation([12, 15, 20], [3, 5, 4], "divide")
    assert result == [4.0, 3.0, 5.0]

    # Test power
    result = await list_operation([2, 3, 4], [3, 2, 2], "power")
    assert result == [8, 9, 16]
    
    # Test modulo
    result = await list_operation([10, 11, 12], [3, 4, 5], "mod")
    assert result == [1, 3, 2]

    # Test empty lists
    result = await list_operation([], [], "add")
    assert result == []

    # Test list_operation with floats
    result = await list_operation([1.5, 2.5], [0.5, 1.5], "add")
    assert result == [2.0, 4.0]
    
    # Test single element lists
    result = await list_operation([5], [3], "multiply")
    assert result == [15]

@pytest.mark.asyncio
async def test_list_operation_error_cases():
    """Test error handling for list operations."""
    # Test different length lists
    with pytest.raises(ValueError, match="Lists must have the same length"):
        await list_operation([1, 2, 3], [4, 5], "add")
    
    # Test invalid operation
    with pytest.raises(ValueError, match="Invalid operation 'invalid'"):
        await list_operation([1, 2], [3, 4], "invalid")
    
    # Test division by zero
    with pytest.raises(ValueError, match="Division by zero encountered"):
        await list_operation([1, 2, 3], [0, 1, 2], "divide")

@pytest.mark.asyncio
async def test_calc_pi_precision():
    """Test pi calculation with different precisions."""
    # Test with small precision
    result = await calc_pi(5)
    assert str(result).startswith("3.14")
    
    # Test with higher precision
    result = await calc_pi(10)
    assert str(result).startswith("3.141592")

