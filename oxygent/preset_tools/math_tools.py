from pydantic import Field

from oxygent.oxy import FunctionHub

math_tools = FunctionHub(name="math_tools")


@math_tools.tool(
    description="A tool for exponentiation that returns the result of n to the power of m."
)
def power(
    n: int = Field(description="base"),
    m: int = Field(description="exponent", default=2),
) -> int:
    import math

    return math.pow(n, m)


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
