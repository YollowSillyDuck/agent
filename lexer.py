import pyparsing as pp

class Lexer:
    def __init__(self):
        self._setup_lexer()
    
    def _setup_lexer(self):
        # 忽略注释和空白
        pp.ParserElement.setDefaultWhitespaceChars(' \t\r\n')
        
        # 单行注释
        comment_line = pp.Literal('//') + pp.restOfLine
        # 多行注释
        comment_block = pp.Literal('/*') + pp.SkipTo('*/', include=True)
        
        # 定义注释忽略
        self.comment = comment_line | comment_block
        self.comment.setParseAction(pp.replaceWith(''))
        
        # 关键字
        keywords = [
            'intent', 'response', 'patterns', 'next_state', 'state', 'on_input',
            'if', 'elif', 'else', 'call', 'reset_state', 'match', 'with',
            'and', 'or', 'not', 'filter', 'sort', 'limit', 'format', 'data',
            'priority', 'contains', 'matches', 'starts_with', 'ends_with', 'exclude',
            'extract', 'detect', 'fallback', 'return', 'by', 'asc', 'desc', 'count',
            'in', 'where', 'default', 'initial', 'regex', 'function'
        ]
        
        # 标识符
        identifier = pp.Word(pp.alphas + '_', pp.alphanums + '_')
        
        # 确保关键字不被识别为标识符
        for keyword in keywords:
            identifier = identifier.copy()
            identifier.addCondition(lambda tokens: tokens[0] != keyword)
        
        # 字符串字面量
        string_literal = pp.QuotedString('"') | pp.QuotedString("'")
        
        # 数值字面量
        number_literal = pp.Combine(pp.Optional('-') + pp.Word(pp.nums) + pp.Optional('.' + pp.Word(pp.nums)))
        number_literal.setParseAction(lambda tokens: float(tokens[0]) if '.' in tokens[0] else int(tokens[0]))
        
        # 布尔字面量
        boolean_literal = pp.Keyword('true') | pp.Keyword('false')
        boolean_literal.setParseAction(lambda tokens: True if tokens[0] == 'true' else False)
        
        # 正则表达式字面量
        regex_literal = pp.Combine(pp.Literal('/') + pp.SkipTo('/', ignore=pp.QuotedString('"') | pp.QuotedString("'")) + '/')
        
        # 变量引用
        variable = pp.Literal('$') + identifier
        
        # 字符串插值
        interpolation = pp.Literal('#{') + pp.SkipTo('}') + pp.Literal('}')
        
        # 运算符和分隔符
        operators = {
            'PLUS': '+', 'MINUS': '-', 'MULTIPLY': '*', 'DIVIDE': '/',
            'EQUALS': '=', 'DOUBLE_EQUALS': '==', 'NOT_EQUALS': '!=',
            'LESS_THAN': '<', 'LESS_EQUALS': '<=', 'GREATER_THAN': '>',
            'GREATER_EQUALS': '>=',
            'LBRACE': '{', 'RBRACE': '}', 'LBRACKET': '[', 'RBRACKET': ']',
            'LPAREN': '(', 'RPAREN': ')', 'COLON': ':', 'SEMICOLON': ';',
            'COMMA': ',', 'DOT': '.', 'ARROW': '=>', 'RETURN_ARROW': '->'
        }
        
        # 定义所有词法单元
        self.tokens = {
            'COMMENT': self.comment,
            'KEYWORD': pp.MatchFirst(pp.Keyword(k) for k in keywords),
            'IDENTIFIER': identifier,
            'STRING_LITERAL': string_literal,
            'NUMBER_LITERAL': number_literal,
            'BOOLEAN_LITERAL': boolean_literal,
            'REGEX_LITERAL': regex_literal,
            'VARIABLE': variable,
            'INTERPOLATION': interpolation,
        }
        
        # 添加运算符
        for name, value in operators.items():
            self.tokens[name] = pp.Literal(value)
        
        # 创建所有标记的组合
        self.all_tokens = pp.MatchFirst(self.tokens.values())
    
    def tokenize(self, code):
        """将DSL代码转换为标记列表"""
        # 先去除注释
        import re
        
        # 去除多行注释
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        # 去除单行注释
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        
        tokens = []
        pos = 0
        
        # 定义关键字列表用于快速检查
        keywords = {
            'intent', 'response', 'patterns', 'next_state', 'state', 'on_input',
            'if', 'elif', 'else', 'call', 'reset_state', 'match', 'with',
            'and', 'or', 'not', 'filter', 'sort', 'limit', 'format', 'data',
            'priority', 'contains', 'matches', 'starts_with', 'ends_with', 'exclude',
            'extract', 'detect', 'fallback', 'return', 'by', 'asc', 'desc', 'count',
            'in', 'where', 'default', 'initial', 'regex', 'function'
        }
        
        # 定义简单的运算符和分隔符
        simple_tokens = {
            '+': 'PLUS', '-': 'MINUS', '*': 'MULTIPLY',
            '=': 'EQUALS', '==': 'DOUBLE_EQUALS', '!=': 'NOT_EQUALS',
            '<': 'LESS_THAN', '<=': 'LESS_EQUALS', '>': 'GREATER_THAN',
            '>=': 'GREATER_EQUALS',
            '{': 'LBRACE', '}': 'RBRACE', '[': 'LBRACKET', ']': 'RBRACKET',
            '(': 'LPAREN', ')': 'RPAREN', ':': 'COLON', ';': 'SEMICOLON',
            ',': 'COMMA', '.': 'DOT', '=>': 'ARROW', '->': 'RETURN_ARROW'
        }
        
        while pos < len(code):
            char = code[pos]
            
            # 跳过空白字符
            if char.isspace():
                pos += 1
                continue
            
            # 尝试匹配双字符运算符
            if pos + 1 < len(code):
                two_chars = code[pos:pos+2]
                if two_chars in simple_tokens:
                    tokens.append((simple_tokens[two_chars], two_chars))
                    pos += 2
                    continue
            
            # 尝试匹配单字符运算符或分隔符（除了斜杠，因为斜杠可能是正则表达式开始）
            if char in simple_tokens and char != '/':
                tokens.append((simple_tokens[char], char))
                pos += 1
                continue
            
            # 处理斜杠：可能是除法运算符或正则表达式开始
            if char == '/':
                # 检查是否是正则表达式
                if self._is_regex_start(code, pos):
                    # 匹配正则表达式
                    regex_start = pos
                    pos += 1  # 跳过开始的 /
                    
                    # 寻找正则表达式结束标记 /，考虑转义字符
                    while pos < len(code) and not (code[pos] == '/' and (pos > 0 and code[pos-1] != '\\')):
                        pos += 1
                    
                    if pos < len(code):
                        pos += 1  # 跳过结束的 /
                        regex_str = code[regex_start:pos]
                        tokens.append(('REGEX_LITERAL', regex_str))
                        continue
                # 如果不是正则表达式，作为除法运算符处理
                tokens.append(('DIVIDE', '/'))
                pos += 1
                continue
            
            # 匹配字符串字面量
            if char in ['"', "'"]:
                quote = char
                string_content = ''
                pos += 1
                while pos < len(code) and code[pos] != quote:
                    if code[pos] == '\\' and pos + 1 < len(code):
                        # 处理转义字符
                        pos += 1
                        if code[pos] == '\\':
                            string_content += '\\'
                        elif code[pos] == '"':
                            string_content += '"'
                        elif code[pos] == "'":
                            string_content += "'"
                        elif code[pos] == 'n':
                            string_content += '\n'
                        else:
                            string_content += code[pos]
                    else:
                        string_content += code[pos]
                    pos += 1
                if pos < len(code):
                    pos += 1  # 跳过结束引号
                tokens.append(('STRING_LITERAL', quote + string_content + quote))
                continue
            
            # 匹配数字字面量
            if char.isdigit() or char == '-':
                num_start = pos
                if char == '-':
                    pos += 1
                if pos < len(code) and code[pos].isdigit():
                    while pos < len(code) and (code[pos].isdigit() or code[pos] == '.'):
                        pos += 1
                    num_str = code[num_start:pos]
                    tokens.append(('NUMBER_LITERAL', num_str))
                    continue
                else:
                    # 只是一个负号，不是数字的一部分
                    tokens.append(('MINUS', '-'))
                    continue
            
            # 匹配标识符、关键字或布尔字面量
            if char.isalpha() or char == '_':
                ident_start = pos
                while pos < len(code) and (code[pos].isalnum() or code[pos] == '_'):
                    pos += 1
                ident = code[ident_start:pos]
                # 首先检查是否是布尔字面量
                if ident == 'true' or ident == 'false':
                    tokens.append(('BOOLEAN_LITERAL', ident))
                # 然后检查是否是关键字
                elif ident in keywords:
                    tokens.append(('KEYWORD', ident))
                else:
                    tokens.append(('IDENTIFIER', ident))
                continue
            
            # 匹配变量引用
            if char == '$':
                pos += 1
                if pos < len(code) and (code[pos].isalpha() or code[pos] == '_'):
                    ident_start = pos
                    while pos < len(code) and (code[pos].isalnum() or code[pos] == '_'):
                        pos += 1
                    var_name = '$' + code[ident_start:pos]
                    tokens.append(('VARIABLE', var_name))
                    continue
                else:
                    # 只是一个$符号，不是变量引用
                    tokens.append(('IDENTIFIER', '$'))
                    continue
            
            # 匹配字符串插值
            if char == '#' and pos + 1 < len(code) and code[pos + 1] == '{':
                interpolation_start = pos
                pos += 2  # 跳过 #{ 
                brace_count = 1
                while pos < len(code) and brace_count > 0:
                    if code[pos] == '{':
                        brace_count += 1
                    elif code[pos] == '}':
                        brace_count -= 1
                    pos += 1
                if brace_count == 0:
                    interpolation = code[interpolation_start:pos]
                    tokens.append(('INTERPOLATION', interpolation))
                    continue
                else:
                    # 不匹配的大括号，回退
                    pos = interpolation_start
            
            # 如果没有匹配到任何类型，记录为错误
            print(f"Warning: Unexpected character '{char}' at position {pos}")
            tokens.append(('UNKNOWN', char))
            pos += 1
        
        return tokens
        
    def _is_regex_start(self, code, pos):
        """判断当前位置的斜杠是否是正则表达式的开始"""
        # 如果是行首，很可能是正则表达式
        if pos == 0:
            return True
        
        # 检查前一个字符
        prev_char = code[pos-1]
        
        # 如果前一个字符是以下情况，很可能是除法运算符：
        # 1. 数字
        # 2. 字母（标识符）
        # 3. 下划线
        # 4. 右括号、右方括号、右大括号
        # 5. 字符串结束引号
        if (prev_char.isalnum() or 
            prev_char == '_' or 
            prev_char in [')', ']', '}', '"', "'"]):
            return False
        
        # 检查上下文，如果在特定上下文中，比如patterns: regex[...]块中，更可能是正则表达式
        # 查找最近的关键字
        context_start = max(0, pos - 50)  # 查看前面50个字符的上下文
        context = code[context_start:pos]
        
        # 如果在patterns: regex[...]块中，更可能是正则表达式
        if 'patterns:' in context and 'regex' in context:
            return True
        
        # 其他情况认为是正则表达式
        return True

# 创建全局lexer实例
_lexer = Lexer()

# 提供独立的tokenize函数，方便直接导入使用
def tokenize(code):
    """将DSL代码转换为标记列表"""
    return _lexer.tokenize(code)

if __name__ == "__main__":
    # 简单测试
    test_code = '''
    // 这是注释
    intent GREETING priority 10 {
        patterns: ["你好", "嗨", "早上好"];
        response: "你好，我是外卖客服助手～";
        next_state: IDLE;
    }
    '''
    # 测试类方法
    lexer = Lexer()
    tokens1 = lexer.tokenize(test_code)
    print("使用Lexer实例:")
    for token in tokens1[:5]:  # 只打印前5个
        print(token)
    
    # 测试独立函数
    tokens2 = tokenize(test_code)
    print("\n使用独立tokenize函数:")
    for token in tokens2[:5]:  # 只打印前5个
        print(token)