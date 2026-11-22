from mcp.server import MCPServer


mcp = MCPServer("utility-server")


@mcp.tool()
def calculator(
    operation: str,
    a: float,
    b: float
) -> dict:
    """
    执行基础数学计算。

    operation 可选：
    - add
    - subtract
    - multiply
    - divide
    """

    if operation == "add":
        result = a + b

    elif operation == "subtract":
        result = a - b

    elif operation == "multiply":
        result = a * b

    elif operation == "divide":

        if b == 0:
            return {
                "error": "除数不能为 0"
            }

        result = a / b

    else:
        return {
            "error": f"不支持的操作: {operation}"
        }

    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result
    }


@mcp.tool()
def get_weather(location: str) -> dict:
    """
    查询指定城市的天气。

    支持中文或英文城市名称，例如：
    - 新加坡 / Singapore
    - 北京 / Beijing
    - 上海 / Shanghai

    当前使用教学 Demo 数据。
    """

    # =========================
    # 地点标准化
    # =========================

    location_aliases = {
        "新加坡": "新加坡",
        "singapore": "新加坡",

        "北京": "北京",
        "beijing": "北京",

        "上海": "上海",
        "shanghai": "上海",
    }

    normalized_input = (
        location
        .strip()
        .lower()
    )

    normalized_location = (
        location_aliases.get(
            normalized_input
        )
    )

    if normalized_location is None:
        return {
            "location": location,
            "error": "暂无该地区天气数据"
        }

    # =========================
    # Demo 天气数据
    # =========================

    weather_data = {
        "新加坡": {
            "temperature": 32,
            "condition": "晴",
        },

        "北京": {
            "temperature": 18,
            "condition": "多云",
        },

        "上海": {
            "temperature": 24,
            "condition": "小雨",
        },
    }

    weather = weather_data[
        normalized_location
    ]

    return {
        "location": normalized_location,
        **weather,
    }

if __name__ == "__main__":
    mcp.run()