from typing import Any, Dict, List, Optional
import os
import sys
import asyncio
import json
import subprocess
import re
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("code_analyzer")

# Constants
SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "java", "go", "ruby", "php", "c", "cpp"]
CACHE_DURATION_MINUTES = 30

# Cache for storing analysis results
analysis_cache = {}


async def run_command(cmd: List[str], cwd: str = None) -> Dict[str, Any]:
    """Run a shell command asynchronously and return stdout/stderr."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        # Add timeout to prevent hanging
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace'),
                "returncode": process.returncode
            }
        except asyncio.TimeoutError:
            # Try to terminate the process if it times out
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
            except:
                pass
            
            return {
                "success": False,
                "error": "Command timed out after 30 seconds",
                "stdout": "",
                "stderr": "Command timed out after 30 seconds",
                "returncode": -1
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }


def detect_language(file_path: str) -> str:
    """Detect programming language based on file extension."""
    ext = Path(file_path).suffix.lower().lstrip('.')
    
    language_map = {
        'py': 'python',
        'js': 'javascript',
        'ts': 'typescript',
        'jsx': 'javascript',
        'tsx': 'typescript',
        'java': 'java',
        'go': 'go',
        'rb': 'ruby',
        'php': 'php',
        'c': 'c',
        'cpp': 'cpp',
        'cc': 'cpp',
        'h': 'c',
        'hpp': 'cpp'
    }
    
    return language_map.get(ext, 'unknown')


def count_lines(file_path: str) -> Dict[str, int]:
    """Count total lines, code lines, comment lines, and blank lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        blank_lines = sum(1 for line in lines if line.strip() == '')
        
        language = detect_language(file_path)
        comment_lines = 0
        
        # Define comment patterns for different languages
        if language == 'python':
            comment_pattern = r'^\s*#'
            docstring_start_pattern = r'^\s*"""'
            in_docstring = False
            
            for line in lines:
                if re.match(docstring_start_pattern, line.strip()):
                    in_docstring = not in_docstring
                    comment_lines += 1
                elif in_docstring or re.match(comment_pattern, line):
                    comment_lines += 1
                    
        elif language in ['javascript', 'typescript', 'java', 'cpp', 'c', 'php']:
            single_comment_pattern = r'^\s*(\/\/|#)'
            multi_comment_start_pattern = r'^\s*\/\*'
            multi_comment_end_pattern = r'\*\/'
            in_multi_comment = False
            
            for line in lines:
                if not in_multi_comment and re.search(single_comment_pattern, line):
                    comment_lines += 1
                elif not in_multi_comment and re.search(multi_comment_start_pattern, line):
                    in_multi_comment = True
                    comment_lines += 1
                elif in_multi_comment:
                    comment_lines += 1
                    if re.search(multi_comment_end_pattern, line):
                        in_multi_comment = False
        
        code_lines = total_lines - blank_lines - comment_lines
        
        return {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "comment_lines": comment_lines,
            "blank_lines": blank_lines,
            "comment_ratio": round(comment_lines / code_lines * 100, 2) if code_lines > 0 else 0
        }
    except Exception as e:
        return {
            "error": str(e),
            "total_lines": 0,
            "code_lines": 0,
            "comment_lines": 0,
            "blank_lines": 0,
            "comment_ratio": 0
        }


def calculate_complexity(file_path: str) -> Dict[str, Any]:
    """Calculate cyclomatic complexity of functions in a file."""
    language = detect_language(file_path)
    
    if language == 'python':
        try:
            result = subprocess.run(
                ['python', '-m', 'radon', 'cc', '-s', file_path],
                capture_output=True,
                text=True,
                check=False,
                timeout=10  # Add timeout to prevent hanging
            )
            
            if result.returncode != 0:
                return {"error": result.stderr, "average_complexity": 0, "functions": []}
            
            # Parse radon output
            functions = []
            total_complexity = 0
            count = 0
            
            for line in result.stdout.splitlines():
                if ' - ' in line:
                    parts = line.split(' - ')
                    if len(parts) >= 2:
                        func_name = parts[0].strip()
                        complexity_part = parts[1].strip().split()[0]  # "A (1)" -> "A"
                        
                        # Fix regex pattern to safely extract complexity value
                        complexity_match = re.search(r'\((\d+)\)', complexity_part)
                        if complexity_match:
                            complexity = int(complexity_match.group(1))
                        else:
                            complexity = 0
                        
                        functions.append({
                            "name": func_name,
                            "complexity": complexity,
                            "risk": complexity_part.split()[0] if ' ' in complexity_part else complexity_part
                        })
                        
                        total_complexity += complexity
                        count += 1
            
            avg_complexity = round(total_complexity / count, 2) if count > 0 else 0
            
            return {
                "average_complexity": avg_complexity,
                "functions": functions
            }
        except Exception as e:
            return {"error": str(e), "average_complexity": 0, "functions": []}
    else:
        return {"error": f"Complexity calculation not supported for {language}", "average_complexity": 0, "functions": []}


async def check_security_issues(file_path: str) -> List[Dict[str, Any]]:
    """Check for security issues in code using appropriate tools."""
    language = detect_language(file_path)
    issues = []
    
    try:
        if language == 'python':
            # Use bandit for Python security analysis
            cmd = ['bandit', '-f', 'json', '-q', file_path]
            result = await run_command(cmd)
            
            if result["success"]:
                try:
                    bandit_results = json.loads(result["stdout"])
                    for issue in bandit_results.get("results", []):
                        issues.append({
                            "line": issue.get("line_number", 0),
                            "severity": issue.get("issue_severity", ""),
                            "confidence": issue.get("issue_confidence", ""),
                            "message": issue.get("issue_text", ""),
                            "code": issue.get("code", "")
                        })
                except json.JSONDecodeError:
                    issues.append({
                        "line": 0,
                        "severity": "error",
                        "confidence": "high",
                        "message": "Failed to parse bandit output",
                        "code": ""
                    })
        elif language in ['javascript', 'typescript']:
            # Use eslint for JavaScript/TypeScript security analysis
            cmd = ['eslint', '--format', 'json', file_path]
            result = await run_command(cmd)
            
            if result["success"] or result["returncode"] == 1:  # eslint returns 1 if issues found
                try:
                    eslint_results = json.loads(result["stdout"])
                    for file_result in eslint_results:
                        for message in file_result.get("messages", []):
                            issues.append({
                                "line": message.get("line", 0),
                                "severity": ["info", "warning", "error"][message.get("severity", 1) - 1],
                                "confidence": "medium",
                                "message": message.get("message", ""),
                                "code": message.get("ruleId", "")
                            })
                except json.JSONDecodeError:
                    issues.append({
                        "line": 0,
                        "severity": "error",
                        "confidence": "high",
                        "message": "Failed to parse eslint output",
                        "code": ""
                    })
    except Exception as e:
        issues.append({
            "line": 0,
            "severity": "error",
            "confidence": "high",
            "message": f"Error running security check: {str(e)}",
            "code": ""
        })
    
    return issues


def suggest_improvements(file_path: str, metrics: Dict[str, Any], security_issues: List[Dict[str, Any]]) -> List[str]:
    """Suggest code improvements based on metrics and security issues."""
    suggestions = []
    
    # Comment ratio suggestions
    comment_ratio = metrics.get("comment_ratio", 0)
    if comment_ratio < 20:
        suggestions.append("Consider adding more comments to improve code readability (current comment ratio: {}%).".format(comment_ratio))
    
    # Complexity suggestions
    avg_complexity = metrics.get("complexity", {}).get("average_complexity", 0)
    if avg_complexity > 10:
        suggestions.append("Overall code complexity is high ({}). Consider refactoring complex functions.".format(avg_complexity))
    
    complex_functions = [f for f in metrics.get("complexity", {}).get("functions", []) if f.get("complexity", 0) > 10]
    if complex_functions:
        for func in complex_functions[:3]:  # Limit to top 3 most complex functions
            suggestions.append("Function '{}' has high complexity ({}). Consider breaking it down into smaller functions.".format(
                func.get("name", ""), func.get("complexity", 0)
            ))
    
    # Security suggestions
    if security_issues:
        high_severity_issues = [i for i in security_issues if i.get("severity") == "high"]
        if high_severity_issues:
            suggestions.append("Fix {} high severity security issues.".format(len(high_severity_issues)))
        
        medium_severity_issues = [i for i in security_issues if i.get("severity") == "medium"]
        if medium_severity_issues:
            suggestions.append("Address {} medium severity security issues.".format(len(medium_severity_issues)))
    
    # Language-specific suggestions
    language = detect_language(file_path)
    if language == 'python':
        suggestions.append("Consider running 'black' for code formatting and 'isort' for import sorting.")
    elif language in ['javascript', 'typescript']:
        suggestions.append("Consider running 'prettier' for code formatting.")
    
    return suggestions


@mcp.tool()
async def analyze_file(file_path: str) -> str:
    """Analyze a single file for code metrics, security issues, and improvement suggestions.
    
    Args:
        file_path: Path to the file to analyze
    """
    if not os.path.isfile(file_path):
        return f"Error: File '{file_path}' does not exist."
    
    language = detect_language(file_path)
    if language == 'unknown':
        return f"Error: Unsupported file type for '{file_path}'."
    
    # Gather metrics
    line_counts = count_lines(file_path)
    complexity = calculate_complexity(file_path)
    security_issues = await check_security_issues(file_path)
    
    # Generate suggestions
    suggestions = suggest_improvements(file_path, {
        "line_counts": line_counts,
        "complexity": complexity,
        "comment_ratio": line_counts.get("comment_ratio", 0)
    }, security_issues)
    
    # Format the report
    report = f"Code Analysis Report for {os.path.basename(file_path)}\n"
    report += f"Language: {language.title()}\n\n"
    
    report += "Line Metrics:\n"
    report += f"  Total Lines: {line_counts.get('total_lines', 0)}\n"
    report += f"  Code Lines: {line_counts.get('code_lines', 0)}\n"
    report += f"  Comment Lines: {line_counts.get('comment_lines', 0)}\n"
    report += f"  Blank Lines: {line_counts.get('blank_lines', 0)}\n"
    report += f"  Comment Ratio: {line_counts.get('comment_ratio', 0)}%\n\n"
    
    report += "Complexity Metrics:\n"
    if "error" in complexity:
        report += f"  Error: {complexity.get('error', '')}\n"
    else:
        report += f"  Average Complexity: {complexity.get('average_complexity', 0)}\n"
        report += "  Complex Functions:\n"
        for func in sorted(complexity.get('functions', []), key=lambda x: x.get('complexity', 0), reverse=True)[:5]:
            report += f"    {func.get('name', '')}: {func.get('complexity', 0)} ({func.get('risk', '')})\n"
    
    report += "\nSecurity Issues:\n"
    if not security_issues:
        report += "  No security issues found.\n"
    else:
        for issue in security_issues[:5]:  # Limit to top 5 issues
            report += f"  Line {issue.get('line', 0)}: [{issue.get('severity', '').upper()}] {issue.get('message', '')}\n"
        if len(security_issues) > 5:
            report += f"  ... and {len(security_issues) - 5} more issues.\n"
    
    report += "\nImprovement Suggestions:\n"
    if not suggestions:
        report += "  No specific suggestions.\n"
    else:
        for i, suggestion in enumerate(suggestions, 1):
            report += f"  {i}. {suggestion}\n"
    
    return report


@mcp.tool()
async def analyze_directory(directory_path: str, file_pattern: str = "*.*") -> str:
    """Analyze all matching files in a directory for code metrics and issues.
    
    Args:
        directory_path: Path to the directory to analyze
        file_pattern: Optional file pattern to match (e.g., "*.py" for Python files)
    """
    if not os.path.isdir(directory_path):
        return f"Error: Directory '{directory_path}' does not exist."
    
    # Find matching files
    matching_files = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            file_path = os.path.join(root, file)
            language = detect_language(file_path)
            if language != 'unknown' and (file_pattern == "*.*" or Path(file).match(file_pattern)):
                matching_files.append(file_path)
    
    if not matching_files:
        return f"No matching files found in '{directory_path}' with pattern '{file_pattern}'."
    
    # Analyze each file
    total_lines = 0
    total_code_lines = 0
    total_comment_lines = 0
    total_blank_lines = 0
    all_security_issues = []
    file_complexities = []
    
    for file_path in matching_files:
        line_counts = count_lines(file_path)
        total_lines += line_counts.get('total_lines', 0)
        total_code_lines += line_counts.get('code_lines', 0)
        total_comment_lines += line_counts.get('comment_lines', 0)
        total_blank_lines += line_counts.get('blank_lines', 0)
        
        complexity = calculate_complexity(file_path)
        if "average_complexity" in complexity:
            file_complexities.append({
                "file": os.path.relpath(file_path, directory_path),
                "complexity": complexity.get("average_complexity", 0)
            })
        
        security_issues = await check_security_issues(file_path)
        for issue in security_issues:
            issue["file"] = os.path.relpath(file_path, directory_path)
            all_security_issues.append(issue)
    
    # Calculate overall metrics
    overall_comment_ratio = round(total_comment_lines / total_code_lines * 100, 2) if total_code_lines > 0 else 0
    avg_complexity = round(sum(item["complexity"] for item in file_complexities) / len(file_complexities), 2) if file_complexities else 0
    
    # Format the report
    report = f"Directory Analysis Report for {directory_path}\n"
    report += f"Files Analyzed: {len(matching_files)}\n\n"
    
    report += "Overall Metrics:\n"
    report += f"  Total Lines: {total_lines}\n"
    report += f"  Code Lines: {total_code_lines}\n"
    report += f"  Comment Lines: {total_comment_lines}\n"
    report += f"  Blank Lines: {total_blank_lines}\n"
    report += f"  Comment Ratio: {overall_comment_ratio}%\n"
    report += f"  Average Complexity: {avg_complexity}\n\n"
    
    report += "Most Complex Files:\n"
    for item in sorted(file_complexities, key=lambda x: x["complexity"], reverse=True)[:5]:
        report += f"  {item['file']}: {item['complexity']}\n"
    
    report += "\nSecurity Issues Summary:\n"
    if not all_security_issues:
        report += "  No security issues found.\n"
    else:
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in all_security_issues:
            severity = issue.get("severity", "low").lower()
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        report += f"  High Severity: {severity_counts['high']}\n"
        report += f"  Medium Severity: {severity_counts['medium']}\n"
        report += f"  Low Severity: {severity_counts['low']}\n\n"
        
        report += "Top Security Issues:\n"
        for issue in sorted(all_security_issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "low").lower(), 3))[:5]:
            report += f"  {issue['file']}:{issue['line']} [{issue['severity'].upper()}] {issue['message']}\n"
    
    return report


@mcp.tool()
async def check_dependencies(project_path: str) -> str:
    """Check for outdated or vulnerable dependencies in a project.
    
    Args:
        project_path: Path to the project directory
    """
    if not os.path.isdir(project_path):
        return f"Error: Directory '{project_path}' does not exist."
    
    # Detect project type
    has_requirements = os.path.isfile(os.path.join(project_path, "requirements.txt"))
    has_pipfile = os.path.isfile(os.path.join(project_path, "Pipfile"))
    has_poetry = os.path.isfile(os.path.join(project_path, "pyproject.toml"))
    has_package_json = os.path.isfile(os.path.join(project_path, "package.json"))
    has_gemfile = os.path.isfile(os.path.join(project_path, "Gemfile"))
    has_composer = os.path.isfile(os.path.join(project_path, "composer.json"))
    
    report = f"Dependency Analysis Report for {project_path}\n\n"
    
    if has_requirements:
        # Check Python dependencies with pip
        cmd = ['pip', 'list', '--outdated', '--format', 'json']
        result = await run_command(cmd, cwd=project_path)
        
        if result["success"]:
            try:
                outdated = json.loads(result["stdout"])
                report += "Python Dependencies (requirements.txt):\n"
                report += f"  Total Outdated Packages: {len(outdated)}\n\n"
                
                if outdated:
                    report += "  Outdated Packages:\n"
                    for pkg in outdated:
                        report += f"    {pkg['name']}: {pkg['version']} -> {pkg['latest_version']}\n"
                else:
                    report += "  All packages are up to date.\n"
            except json.JSONDecodeError:
                report += "  Error parsing pip output.\n"
        else:
            report += f"  Error checking Python dependencies: {result['stderr']}\n"
        
        # Check for security vulnerabilities with safety
        cmd = ['safety', 'check', '--json', '-r', os.path.join(project_path, "requirements.txt")]
        result = await run_command(cmd)
        
        if result["success"] or result["returncode"] == 64:  # safety returns 64 if vulnerabilities found
            try:
                vulnerabilities = json.loads(result["stdout"])
                report += "\n  Security Vulnerabilities:\n"
                
                if vulnerabilities:
                    for vuln in vulnerabilities:
                        report += f"    {vuln[0]}: {vuln[3]}\n"
                else:
                    report += "    No known vulnerabilities found.\n"
            except json.JSONDecodeError:
                report += "    Error parsing safety output.\n"
    elif has_package_json:
        # Check JavaScript/TypeScript dependencies with npm
        cmd = ['npm', 'outdated', '--json']
        result = await run_command(cmd, cwd=project_path)
        
        if result["success"] or result["returncode"] == 1:  # npm returns 1 if outdated packages found
            try:
                outdated = json.loads(result["stdout"])
                report += "JavaScript/TypeScript Dependencies (package.json):\n"
                report += f"  Total Outdated Packages: {len(outdated)}\n\n"
                
                if outdated:
                    report += "  Outdated Packages:\n"
                    for pkg_name, pkg_info in outdated.items():
                        report += f"    {pkg_name}: {pkg_info.get('current', 'unknown')} -> {pkg_info.get('latest', 'unknown')}\n"
                else:
                    report += "  All packages are up to date.\n"
            except json.JSONDecodeError:
                report += "  Error parsing npm output.\n"
        else:
            report += f"  Error checking JavaScript dependencies: {result['stderr']}\n"
        
        # Check for security vulnerabilities with npm audit
        cmd = ['npm', 'audit', '--json']
        result = await run_command(cmd, cwd=project_path)
        
        if result["success"] or result["returncode"] == 1:  # npm audit returns 1 if vulnerabilities found
            try:
                audit_result = json.loads(result["stdout"])
                vulnerabilities = audit_result.get("vulnerabilities", {})
                
                report += "\n  Security Vulnerabilities:\n"
                if vulnerabilities:
                    severity_counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0}
                    
                    for _, vuln_info in vulnerabilities.items():
                        severity = vuln_info.get("severity", "").lower()
                        if severity in severity_counts:
                            severity_counts[severity] += 1
                    
                    report += f"    Critical: {severity_counts['critical']}\n"
                    report += f"    High: {severity_counts['high']}\n"
                    report += f"    Moderate: {severity_counts['moderate']}\n"
                    report += f"    Low: {severity_counts['low']}\n"
                    
                    # List top vulnerabilities
                    report += "\n  Top Vulnerabilities:\n"
                    count = 0
                    for pkg_name, vuln_info in vulnerabilities.items():
                        if count >= 5:  # Limit to 5 vulnerabilities
                            break
                        
                        severity = vuln_info.get("severity", "").upper()
                        via = vuln_info.get("via", [])
                        if isinstance(via, list) and via and isinstance(via[0], dict):
                            title = via[0].get("title", "Unknown")
                        else:
                            title = "Unknown"
                        
                        report += f"    {pkg_name} [{severity}]: {title}\n"
                        count += 1
                else:
                    report += "    No known vulnerabilities found.\n"
            except json.JSONDecodeError:
                report += "    Error parsing npm audit output.\n"
    else:
        report += "No supported dependency files found (requirements.txt, package.json).\n"
        report += "Supported project types: Python (requirements.txt), JavaScript/TypeScript (package.json).\n"
    
    return report


def main():
    """Run the Code Analyzer MCP server."""
    if len(sys.argv) > 1:
        # If arguments are provided, run the MCP server
        mcp.run(transport='stdio')
    else:
        # Otherwise, run a simple test
        async def test():
            # Test file analysis
            print("Testing file analysis...")
            test_file = os.path.abspath(__file__)
            analysis = await analyze_file(test_file)
            print(analysis)
            
            # Test with a smaller scope to avoid timeout
            print("\nTesting directory analysis (limited scope)...")
            test_dir = os.path.dirname(os.path.abspath(__file__))
            # Only analyze the current file to keep the test quick
            dir_analysis = await analyze_directory(test_dir, os.path.basename(__file__))
            print(dir_analysis)
            
            # Test dependency check
            print("\nTesting dependency check...")
            dep_analysis = await check_dependencies(test_dir)
            print(dep_analysis)
        
        # Run the test with proper error handling
        try:
            asyncio.run(test())
        except KeyboardInterrupt:
            print("\nTest interrupted by user.")
        except Exception as e:
            print(f"\nError during test: {e}")


if __name__ == "__main__":
    main()