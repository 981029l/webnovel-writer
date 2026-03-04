# Copyright (c) 2026 左岚. All rights reserved.
"""通用工具函数"""

def chinese_to_arabic(cn: str) -> int:
    """中文数字转阿拉伯数字"""
    cn_map = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '百': 100, '千': 1000, '万': 10000
    }
    
    # 简单情况
    if cn in cn_map:
        val = cn_map[cn]
        # 特殊处理 '十' (10), '百' (100) 单独出现
        return val

    # 复杂情况处理
    total = 0
    sub_unit = 1 # 当前位的单位 (个, 十, 百...)
    result = 0
    tmp = 0
    
    # 从左向右遍历（这也是一种常见思路，或者从右向左）
    # 这里采用一种通用的累加逻辑
    
    # 更简单的常用解析逻辑：
    # 遍历字符串，如果是单位，则 tmp * unit，累加到 section
    # 如果是数字，tmp = digit
    
    # 针对 "一千二百三十四"
    
    unit_map = {'十': 10, '百': 100, '千': 1000, '万': 10000}
    digit_map = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9
    }
    
    current_val = 0
    last_unit = 1
    
    # 检查是否仅有十开头，如 "十二" -> "一十二"
    if cn.startswith('十'):
        cn = '一' + cn
        
    for char in cn:
        if char in digit_map:
            current_val = digit_map[char]
        elif char in unit_map:
            unit = unit_map[char]
            if unit == 10000:
                result += (total + current_val) * unit
                total = 0
                current_val = 0
            else:
                total += current_val * unit
                current_val = 0
                
    result += total + current_val
    return result
