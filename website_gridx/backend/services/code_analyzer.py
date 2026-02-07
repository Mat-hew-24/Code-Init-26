"""
Code Analyzer - Analyzes Python code for potential infinite loops and resource issues
"""

import ast
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CodeIssue:
    type: str  # 'infinite_loop', 'resource_heavy', 'warning'
    severity: str  # 'high', 'medium', 'low'
    line: int
    message: str
    suggestion: Optional[str] = None


class CodeAnalyzer:
    """Analyzes Python code for potential issues before execution"""
    
    def __init__(self):
        self.infinite_loop_patterns = [
            # While True patterns
            r'\bwhile\s+True\s*:',
            r'\bwhile\s+1\s*:',
            r'\bwhile\s+not\s+False\s*:',
            
            # For loop patterns that might be infinite
            r'for\s+\w+\s+in\s+itertools\.count\(\)',
            r'for\s+\w+\s+in\s+range\([^)]*\):\s*\n\s*continue',
            
            # Recursive patterns without base case
            r'def\s+(\w+).*:\s*.*\1\(',
        ]
        
        self.resource_heavy_patterns = [
            # Large data operations
            r'range\(\s*\d{6,}\s*\)',  # Range with > 100k iterations
            r'\.read\(\)',  # File reading without size limits
            r'requests\.get\(',  # Network requests
            r'urllib\.request',
            r'subprocess\.',
            
            # Memory intensive operations
            r'\[\s*\w+\s*\*\s*\d{4,}\s*\]',  # Large list comprehensions
            r'numpy\.zeros\(\s*\d{5,}',  # Large numpy arrays
        ]

    def analyze_code(self, code: str) -> Tuple[List[CodeIssue], bool]:
        """
        Analyze code and return issues and whether execution should be allowed
        Returns: (issues, should_execute)
        """
        issues = []
        should_execute = True
        
        # Basic syntax check
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(CodeIssue(
                type="syntax_error",
                severity="high", 
                line=e.lineno or 0,
                message=f"Syntax error: {e.msg}",
                suggestion="Fix syntax errors before execution"
            ))
            return issues, False
        
        # Check for infinite loop patterns
        infinite_loop_issues = self._check_infinite_loops(code)
        issues.extend(infinite_loop_issues)
        
        # Check for resource-heavy operations
        resource_issues = self._check_resource_usage(code)
        issues.extend(resource_issues)
        
        # Check AST for more complex patterns
        ast_issues = self._analyze_ast(code)
        issues.extend(ast_issues)
        
        # Determine if execution should proceed
        high_severity_count = sum(1 for issue in issues if issue.severity == "high")
        if high_severity_count > 0:
            should_execute = False
            
        return issues, should_execute

    def _check_infinite_loops(self, code: str) -> List[CodeIssue]:
        """Check for obvious infinite loop patterns"""
        issues = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            for pattern in self.infinite_loop_patterns:
                if re.search(pattern, line):
                    # Check for break statements in the loop
                    loop_end = self._find_loop_end(lines, i-1)
                    has_break = any('break' in lines[j] for j in range(i, min(len(lines), loop_end)))
                    has_return = any('return' in lines[j] for j in range(i, min(len(lines), loop_end)))
                    
                    if not has_break and not has_return:
                        issues.append(CodeIssue(
                            type="infinite_loop",
                            severity="high",
                            line=i,
                            message="Potential infinite loop detected with no break condition",
                            suggestion="Add a break condition or use a different loop structure"
                        ))
                    else:
                        issues.append(CodeIssue(
                            type="infinite_loop",
                            severity="medium",
                            line=i,
                            message="Loop with 'while True' pattern detected (has break/return)",
                            suggestion="Consider using a more explicit condition"
                        ))
        
        return issues

    def _check_resource_usage(self, code: str) -> List[CodeIssue]:
        """Check for resource-intensive operations"""
        issues = []
        lines = code.split('\n')
        
        for i, line in enumerate(lines, 1):
            for pattern in self.resource_heavy_patterns:
                if re.search(pattern, line):
                    issues.append(CodeIssue(
                        type="resource_heavy",
                        severity="medium",
                        line=i,
                        message="Resource-intensive operation detected",
                        suggestion="Consider adding progress monitoring or limits"
                    ))
        
        return issues

    def _analyze_ast(self, code: str) -> List[CodeIssue]:
        """Analyze AST for complex patterns"""
        issues = []
        
        try:
            tree = ast.parse(code)
            
            # Check for nested loops without breaks
            for node in ast.walk(tree):
                if isinstance(node, (ast.While, ast.For)):
                    if hasattr(node, 'lineno'):
                        # Check for deeply nested loops
                        nested_loops = self._count_nested_loops(node)
                        if nested_loops > 2:
                            issues.append(CodeIssue(
                                type="warning",
                                severity="medium",
                                line=node.lineno,
                                message=f"Deeply nested loops ({nested_loops} levels) detected",
                                suggestion="Consider refactoring to reduce nesting"
                            ))
                        
                        # Check recursive function calls
                        if isinstance(node, ast.While):
                            if isinstance(node.test, ast.Constant) and node.test.value is True:
                                # while True loop - check for break conditions
                                has_break = self._has_break_in_body(node.body)
                                if not has_break:
                                    issues.append(CodeIssue(
                                        type="infinite_loop",
                                        severity="high",
                                        line=node.lineno,
                                        message="while True loop without break statement",
                                        suggestion="Add break condition to prevent infinite loop"
                                    ))
                                    
        except Exception:
            # If AST analysis fails, don't block execution
            pass
            
        return issues

    def _find_loop_end(self, lines: List[str], start_line: int) -> int:
        """Find the end line of a loop block"""
        indent_level = len(lines[start_line]) - len(lines[start_line].lstrip())
        
        for i in range(start_line + 1, len(lines)):
            line = lines[i].strip()
            if not line:  # Empty line
                continue
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            if current_indent <= indent_level and line:
                return i
                
        return len(lines)

    def _count_nested_loops(self, node: ast.AST) -> int:
        """Count nested loops in an AST node"""
        max_depth = 0
        
        def count_depth(n, current_depth=0):
            nonlocal max_depth
            if isinstance(n, (ast.While, ast.For)):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            
            for child in ast.iter_child_nodes(n):
                count_depth(child, current_depth)
        
        count_depth(node)
        return max_depth

    def _has_break_in_body(self, body: List[ast.AST]) -> bool:
        """Check if a loop body contains break statements"""
        for node in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(node, ast.Break):
                return True
        return False

    def suggest_safe_patterns(self, code: str) -> List[str]:
        """Suggest safer alternatives for problematic code patterns"""
        suggestions = []
        
        if re.search(r'\bwhile\s+True\s*:', code):
            suggestions.append(
                "Consider using 'for i in range(max_iterations)' with a reasonable limit"
            )
            suggestions.append(
                "Add a counter variable and check it in the while condition"
            )
        
        if re.search(r'range\(\s*\d{6,}\s*\)', code):
            suggestions.append(
                "For large ranges, consider using generators or batch processing"
            )
            suggestions.append(
                "Add progress monitoring: if i % 1000 == 0: print(f'Progress: {i}')"
            )
        
        return suggestions


def analyze_python_code(code: str) -> Dict:
    """Convenience function to analyze Python code and return results"""
    analyzer = CodeAnalyzer()
    issues, should_execute = analyzer.analyze_code(code)
    suggestions = analyzer.suggest_safe_patterns(code)
    
    return {
        "should_execute": should_execute,
        "issues": [
            {
                "type": issue.type,
                "severity": issue.severity,
                "line": issue.line,
                "message": issue.message,
                "suggestion": issue.suggestion
            }
            for issue in issues
        ],
        "suggestions": suggestions,
        "analysis_summary": {
            "total_issues": len(issues),
            "high_severity": sum(1 for i in issues if i.severity == "high"), 
            "medium_severity": sum(1 for i in issues if i.severity == "medium"),
            "low_severity": sum(1 for i in issues if i.severity == "low")
        }
    }