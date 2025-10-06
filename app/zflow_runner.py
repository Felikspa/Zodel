"""
Zflow 语言解析与执行模块。

本模块定义了 ZflowRunner 类，它负责：
1. 解析用户输入的 Zflow 脚本字符串。
2. 将脚本分解为变量定义和工作流结构 (AST)。
3. 按照工作流的定义，一步步调用外部传入的 LLM API 函数来执行整个流程。
"""

import re
import json
from typing import Callable, Generator, List, Dict, Optional
try:
    from app.helper import get_model_type
except:
    pass
class ZflowRunner:
    """
    解析并执行 Zflow 脚本的运行器。
    它将 Zflow 代码解析为变量和 AST，然后通过回调函数执行 LLM 调用。
    """

    def __init__(self, stream_callback: Callable, embedding_callback: Callable=None):
        """
        初始化运行器。
        :param stream_callback: 用于调用 Chat LLM API 的流式函数。
        :param embedding_callback: 用于调用 Embedding LLM API 的函数。
        """
        self.stream_chat = stream_callback
        self.get_embeddings = embedding_callback
        
        # 正则表达式定义
        self.operator_pattern = re.compile(r'^\s*([A-Z])_([a-z][a-zA-Z0-9]*)(?:\((i[a-zA-Z0-9]*)\))?\s*$')
        self.var_start_pattern = re.compile(r'\s*((?:[A-Z]|i[a-zA-Z0-9]*|p[a-zA-Z0-9]*)\s*=)')
        self.workflow_start_pattern = re.compile(r'(i[a-zA-Z0-9]*\s*(?:\[|->))')
        
        # 状态变量
        self._reset()

    def _reset(self):
        """重置解析器的内部状态，以便解析新的代码。"""
        self.variables = {"models": {}, "inputs": {}, "prompts": {}}
        self.workflow_ast = {}
        self.errors = []
        # 用于调试输出的格式化代码
        self.formatted_assignments = "" 
        self.formatted_workflow = ""

    def _log_error(self, message: str, statement: str = ""):
        """
        记录一条解析或执行错误。

        Args:
            message (str): 错误信息的主体。
            statement (str, optional): 导致错误的相关代码片段。
        """
        error_message = f"Error: {message}"
        if statement:
            display_statement = statement[:70] + "..." if len(statement) > 70 else statement
            error_message += f" in statement: '{display_statement}'"
        self.errors.append(error_message)

    def _parse_single_assignment(self, var_name: str, value: str, original_statement: str = ""):
        """解析并存储单个 'VAR = VALUE' 形式的赋值。"""
        var_name, value = var_name.strip(), value.strip()
        
        if not var_name or not value:
            self._log_error("Assignment variable or value is empty", original_statement)
            return

        # 根据变量名格式，存入对应的字典
        if re.fullmatch(r'[A-Z]', var_name):
            self.variables["models"][var_name] = value
        elif re.fullmatch(r'i[a-zA-Z0-9]*', var_name):
            self.variables["inputs"][var_name] = value
        elif re.fullmatch(r'p[a-zA-Z0-9]*', var_name):
            self.variables["prompts"][var_name] = value
        else:
            self._log_error(f"Invalid variable name format '{var_name}'", original_statement)

    def _parse_assignments_from_text(self, text_block: str):
        """从一个可能包含多行或单行多个赋值的文本块中解析所有变量。"""
        # 将所有空白符（包括换行、多个空格）替换为单个空格，以便于正则处理
        normalized_text = re.sub(r'\s+', ' ', text_block).strip()
        
        # 查找所有变量赋值的起始点 (e.g., "A =", "i1 =", "p_x =")
        matches = list(self.var_start_pattern.finditer(normalized_text))
        if not matches:
            if normalized_text:
                self._log_error("Unrecognized content in assignments block", normalized_text)
            return
        
        formatted_statements = []
        for i, match in enumerate(matches):
            # 提取变量名
            var_name_part = match.group(1)
            var_name = var_name_part.replace('=', '').strip()
            
            # 值的范围是从当前等号之后，到下一个变量赋值之前
            value_start_index = match.end()
            value_end_index = matches[i+1].start() if i + 1 < len(matches) else len(normalized_text)
            
            value = normalized_text[value_start_index:value_end_index].strip()
            
            # 如果值以逗号结尾，说明逗号是语句分隔符，而不是值的一部分。
            if value.endswith(','):
                value = value[:-1].strip()

            # 格式化并存储，用于 debug 输出
            formatted_statements.append(f"{var_name} = {value}")
            
            # 解析单个赋值
            self._parse_single_assignment(var_name, value, f"{var_name}={value}")

        self.formatted_assignments = "\n".join(formatted_statements)

    def _handle_loops(self, workflow_str: str) -> str:
        """在解析前，将所有循环结构 '[->...]*N' 展开为重复的字符串。"""
        loop_pattern = re.compile(r'(\[->.*?\])\*(\d+)')

        def expand_match(match):
            content_to_repeat = match.group(1)[1:-1] # 去掉方括号
            repeat_count = int(match.group(2))
            
            if repeat_count <= 0:
                self._log_error("Loop repetition count must be a positive integer", match.group(0)) 
                return ""
            
            return content_to_repeat * repeat_count

        return loop_pattern.sub(expand_match, workflow_str)

    def _parse_operator_node(self, node_str: str) -> Optional[Dict]:
        """解析单个算子节点字符串，如 'A_p1(i2)'。"""
        match = self.operator_pattern.match(node_str)
        if not match:
            self._log_error(f"Invalid operator syntax '{node_str}'")
            return None
        
        model, prompt, extra_input = match.groups()
        return {"type": "operator", "model": model, "prompt": prompt, "extra_input": extra_input}

    def _parse_workflow_stage(self, stage_str: str) -> Optional[Dict]:
        """解析工作流中的一个阶段（可能是单个算子或并发块）。"""
        stage_str = stage_str.strip()
        if stage_str.startswith('{') and stage_str.endswith('}'):
            content = stage_str[1:-1]
            if not content.strip():
                self._log_error("Parallel block '{}' cannot be empty.", stage_str)
                return None
            
            node_strs = [s.strip() for s in content.split(',') if s.strip()]
            nodes = [self._parse_operator_node(ns) for ns in node_strs]
            valid_nodes = [node for node in nodes if node is not None]

            if not valid_nodes and node_strs:
                self._log_error("Invalid content within parallel block", stage_str)
                return None
            
            return {"type": "parallel", "nodes": valid_nodes}
        else:
            return self._parse_operator_node(stage_str)

    def _parse_workflow(self, statement: str):
        """解析完整的工作流语句，构建 AST。"""
        if self.workflow_ast:
            self._log_error("Multiple workflow definitions found. Only one is allowed.", statement) 
            return

        expanded_wf = self._handle_loops(statement)
        self.formatted_workflow = expanded_wf # 存储格式化后的工作流

        stages = [s.strip() for s in expanded_wf.split('->') if s.strip()]
        
        if len(stages) < 2:
            self._log_error("Workflow must contain at least one '->' operator and a starting input.", statement) 
            return
            
        start_input = stages[0]
        if not re.fullmatch(r'i[a-zA-Z0-9]*', start_input):
            self._log_error(f"Workflow must start with an input variable (e.g., i, i1), but found '{start_input}'", statement) 
            return

        flow_steps = [self._parse_workflow_stage(s) for s in stages[1:]]
        self.workflow_ast = {"start_input": start_input, "flow": [step for step in flow_steps if step]}

    def parse(self, code: str):
        """
        主解析函数：从完整的 Zflow 脚本中分离赋值语句和工作流，然后分别解析。
        """
        self._reset()
        assignment_block, workflow_statement = [], ""
        
        for line in code.split('\n'):
            stripped_line = line.strip()
            if not stripped_line: continue
            
            match = self.workflow_start_pattern.search(stripped_line)
            if match:
                # 如果一行中包含工作流的起始模式
                pre_workflow_content = stripped_line[:match.start()]
                if pre_workflow_content.strip():
                    assignment_block.append(pre_workflow_content)
                
                workflow_statement += stripped_line[match.start():].strip()
            else:
                # 否则，整行都属于赋值部分
                assignment_block.append(line)

        # 解析分离出的两部分
        if assignment_block:
            self._parse_assignments_from_text(" ".join(assignment_block))
        if workflow_statement:
            self._parse_workflow(workflow_statement)
        else:
            self._log_error("No workflow statement ('->') found in the code.")

    def execute_stream(self, code: str) -> Generator[str, None, None]:
        """
        解析并流式执行 Zflow 代码。这是 Runner 的核心公共方法。

        Args:
            code (str): 用户输入的完整 Zflow 脚本。

        Yields:
            Generator[str, None, None]: 逐步产生执行过程中的日志和模型输出。
        """
        self.parse(code)
        if self.errors:
            yield "**[Zflow Parse Error]**\n"
            for error in self.errors:
                yield f"- {error}\n"
            return
            
        if not self.workflow_ast:
            yield "**[Zflow Execution Error]**\n- No valid workflow found to execute."
            return

        start_input_var = self.workflow_ast.get("start_input")
        current_input_str = self.variables["inputs"].get(start_input_var)
        if current_input_str is None:
            yield f"**[Zflow Execution Error]**\n- Start input variable '{start_input_var}' is not defined."
            return

        for i, stage in enumerate(self.workflow_ast.get("flow", [])):
            yield f"\n\n---\n**Executing Stage {i+1}**\n---\n"
            stage_outputs = []
            
            nodes_to_run = stage.get('nodes', [stage]) if stage['type'] == 'parallel' else [stage]

            for node in nodes_to_run:
                model_var, prompt_var, extra_input_var = node.get("model"), node.get("prompt"), node.get("extra_input")
                model_name = self.variables["models"].get(model_var)
                prompt_content = self.variables["prompts"].get(prompt_var)
                
                if not model_name or not prompt_content:
                    yield f"\n**[Skip]** Node {model_var}_{prompt_var}: Model or Prompt variable not defined. "
                    continue
                
                final_input = current_input_str
                if extra_input_var:
                    extra_input_content = self.variables["inputs"].get(extra_input_var)
                    if extra_input_content is None:
                        yield f"\n**[Warning]** Extra input '{extra_input_var}' for node {model_var}_{prompt_var} not defined. Ignoring."
                    else:
                        final_input += "\n\n" + extra_input_content
                
                yield f"\n**Model:** `{model_name}`\n\n"
                messages = [{"role": "system", "content": prompt_content}, {"role": "user", "content": final_input}]
                
                try:
                    provider, pure_model_name = model_name.split(':', 1)
                    provider = provider.lower()
                    
                    # --- 核心改动：根据模型类型进行调度 ---
                    model_type = get_model_type(pure_model_name)
                    
                    if model_type == 'chat':
                        # b. 构建 chat messages
                        messages = [
                            {"role": "system", "content": prompt_content},
                            {"role": "user", "content": final_input}
                        ]
                        # c. 调用 Chat LLM 并流式输出
                        full_node_output = ""
                        for chunk in self.stream_chat(provider, pure_model_name, messages):
                            yield chunk
                            full_node_output += chunk
                        stage_outputs.append(full_node_output)

                    elif model_type == 'embedding':
                        # b. Embedding 模型不需要 system prompt，直接使用 final_input
                        yield "(Running Embedding model...)\n"
                        embedding_vector = self.get_embeddings(provider, pure_model_name, final_input)
                        
                        # c. 将向量结果转换为字符串输出到前端
                        output_str = f"Embedding Vector (first 5 dims): {embedding_vector[:5]}..."
                        yield output_str
                        stage_outputs.append(output_str) # 下一阶段的输入是这个字符串

                except Exception as e:
                    yield f"\n\n**[Execution Error]** Failed to call model {model_name}: {e}"
            
            # d. 更新下一步的输入
            current_input_str = "\n\n".join(stage_outputs)

        yield "\n\n---\n**Zflow Execution Finished**\n---"

    def debug(self, code: str):
        """调试函数：解析代码并以易于阅读的格式打印所有解析结果和错误。"""
        print("================ ZFLOW PARSER DEBUG ================")
        self.parse(code)
        
        print("1. Formatted Code (as understood by parser):")
        print("---------------------------------------------")
        print(self.formatted_assignments)
        print(self.formatted_workflow)
        print("\n")

        print("2. Parsed Variables:")
        print("--------------------")
        print(json.dumps(self.variables, indent=2, ensure_ascii=False))
        print("\n")
        
        print("3. Parsed Workflow (AST):")
        print("-------------------------")
        print(json.dumps(self.workflow_ast, indent=2) if self.workflow_ast else "No valid workflow was parsed.")
        print("\n")
        
        print("4. Parser Errors:")
        print("-----------------")
        if self.errors:
            for error in self.errors:
                print(f"- {error}")
        else:
            print("No errors detected. Parsing successful.")
        print("================== END OF DEBUG ==================")

if __name__ == "__main__":
    # 此代码块仅在直接运行 `python zflow_runner.py` 时执行，用于独立测试
    test_code ='''
A= GenStudio:qwen2.5-vl-72b-instruct,B= GenStudio:deepseek-v3,C=GenStudio:deepseek-v3.2-exp
i=’维特根斯坦晚期为什么会发生重大的思想转变，与早期思想截然不同？’
p1=’接下来我会给你一道题目，你的任务是解决它的一部分，具体地说，你需要对发生这种情况的内部原因给出简明扼要的解答，其他角度的回答和多余的输出都应该避免。’
p2=’ 接下来我会给你一道题目，你的任务是解决它的一部分，具体地说，你需要对发生这种情况的外部原因给出简明扼要的解答，其他角度的回答和多余的输出都应该避免。’
p3=’现在有两个模型分别对我给出的题目做出两个角度的解答，请你帮我把它们的观点简明扼要地整合到一起，形成一份完整的答案。如果你没有收到来自前两个模型的回答，就直接返回错误信息。’
i->{A_p1,B_p2}->C_p3(i)
    '''
    dummy_callback = lambda provider, model, messages: iter([f"Streaming response from {provider}:{model}... "])
    runner_for_debug = ZflowRunner(stream_callback=dummy_callback)
    runner_for_debug.debug(test_code)