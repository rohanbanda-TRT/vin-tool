import os
import subprocess
import json
from typing import Dict, Any, List, Optional, Tuple
from fastmcp import FastMCP

app = FastMCP()

@app.tool("get_changed_files")
async def get_changed_files() -> Dict[str, Any]:
    """
    Get a list of all changed files in the git repository.
    
    This tool detects and lists all modified, added, deleted, and untracked files
    in the current git repository. It shows the status of each file and provides
    a summary of the repository's current state.
    
    Returns:
        Dictionary containing the list of changed files and their status
    """
    try:
        # Make sure we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0 or result.stdout.strip() != "true":
            return {
                "success": False,
                "error": "Not inside a git repository"
            }
        
        # Get the status of files in the repository
        status_cmd = ["git", "status", "--porcelain", "-uall"]  # Show all untracked files
            
        status_result = subprocess.run(
            status_cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if status_result.returncode != 0:
            return {
                "success": False,
                "error": f"Git command failed: {status_result.stderr}"
            }
        
        # Parse the status output
        changed_files = []
        for line in status_result.stdout.strip().split("\n"):
            if not line:
                continue
                
            status_code = line[:2]
            file_path = line[3:].strip()
            
            # Handle renamed files
            original_path = None
            if " -> " in file_path:
                original_path, file_path = file_path.split(" -> ")
            
            # Map status codes to human-readable status
            status_map = {
                "A": "added",
                "M": "modified",
                "D": "deleted",
                "R": "renamed",
                "C": "copied",
                "U": "unmerged",
                "?": "untracked",
                "!": "ignored"
            }
            
            # First character is for staging area, second for working directory
            index_status = status_code[0]
            worktree_status = status_code[1] if len(status_code) > 1 else " "
            
            # Determine the overall status
            if index_status == "?" and worktree_status == "?":
                status_text = "untracked"
            elif index_status == "!" and worktree_status == "!":
                status_text = "ignored"
            elif worktree_status != " " and worktree_status in status_map:
                status_text = status_map[worktree_status]
            elif index_status != " " and index_status in status_map:
                status_text = f"staged_{status_map[index_status]}"
            else:
                status_text = "unknown"
            
            file_info = {
                "status": status_text,
                "filename": file_path,
                "index_status": index_status,
                "worktree_status": worktree_status
            }
            
            if original_path:
                file_info["original_filename"] = original_path
                
            changed_files.append(file_info)
        
        # Get branch information
        branch_cmd = ["git", "branch", "--show-current"]
        branch_result = subprocess.run(
            branch_cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        
        # Get repository status summary
        summary_cmd = ["git", "status", "--short", "--branch"]
        summary_result = subprocess.run(
            summary_cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        repo_summary = summary_result.stdout.strip() if summary_result.returncode == 0 else ""
        
        return {
            "success": True,
            "branch": current_branch,
            "repo_summary": repo_summary,
            "changed_files_count": len(changed_files),
            "changed_files": changed_files
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Git command failed: {e.stderr}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error: {str(e)}"
        }

@app.tool("get_file_diff")
async def get_file_diff(file_path: str, diff_type: str = "all") -> Dict[str, Any]:
    """
    Get the detailed diff for a specific file in the git repository.
    
    This tool shows the exact changes made to a file, including added and removed lines.
    It can show all changes, only staged changes, or only unstaged changes.
    
    Args:
        file_path: Path to the file to check
        diff_type: Type of diff to get (all, staged, unstaged)
    
    Returns:
        Dictionary containing the detailed changes for the file
    """
    try:
        # Make sure we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0 or result.stdout.strip() != "true":
            return {
                "success": False,
                "error": "Not inside a git repository"
            }
        
        # Get the status of the file
        status_cmd = ["git", "status", "--porcelain", "--", file_path]
        status_result = subprocess.run(
            status_cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if status_result.returncode != 0:
            return {
                "success": False,
                "error": f"Git command failed: {status_result.stderr}"
            }
        
        if not status_result.stdout.strip():
            return {
                "success": False,
                "error": f"File {file_path} has no changes"
            }
        
        # Parse the status output
        status_line = status_result.stdout.strip().split("\n")[0]
        status_code = status_line[:2]
        
        # First character is for staging area, second for working directory
        index_status = status_code[0]
        worktree_status = status_code[1] if len(status_code) > 1 else " "
        
        # Determine the file status
        status_map = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "U": "unmerged",
            "?": "untracked",
            "!": "ignored"
        }
        
        if index_status == "?" and worktree_status == "?":
            file_status = "untracked"
        elif index_status == "!" and worktree_status == "!":
            file_status = "ignored"
        else:
            file_status = "modified"  # Default to modified for other cases
        
        detailed_changes = []
        
        # For untracked files, just get the content
        if file_status == "untracked":
            try:
                with open(file_path, 'r', errors='replace') as f:
                    content = f.read()
                
                lines_added = []
                line_number = 1
                for line in content.split("\n"):
                    lines_added.append({
                        "line_number": line_number,
                        "content": line
                    })
                    line_number += 1
                
                detailed_changes.append({
                    "filename": file_path,
                    "status": "untracked",
                    "lines_added": lines_added,
                    "lines_removed": []
                })
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error reading file: {str(e)}"
                }
        else:
            # For tracked files with changes, get the diff
            changes_to_check = []
            
            if diff_type in ["all", "unstaged"] and worktree_status not in [" ", "?"]:
                changes_to_check.append(("unstaged", ["git", "diff", "--", file_path]))
            
            if diff_type in ["all", "staged"] and index_status not in [" ", "?"]:
                changes_to_check.append(("staged", ["git", "diff", "--cached", "--", file_path]))
            
            for change_type, diff_cmd in changes_to_check:
                diff_result = subprocess.run(
                    diff_cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if diff_result.returncode != 0 or not diff_result.stdout.strip():
                    continue
                
                # Parse the diff to extract line changes
                lines_added = []
                lines_removed = []
                current_line_number = 0
                
                for line in diff_result.stdout.split("\n"):
                    if line.startswith("@@"):
                        # Extract line numbers from the @@ -a,b +c,d @@ format
                        line_info = line.split("@@")[1].strip()
                        added_part = line_info.split(" ")[1]
                        current_line_number = int(added_part.split(",")[0].replace("+", ""))
                    elif line.startswith("+") and not line.startswith("+++"):
                        lines_added.append({
                            "line_number": current_line_number,
                            "content": line[1:]
                        })
                        current_line_number += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        lines_removed.append({
                            "content": line[1:]
                        })
                    elif not line.startswith("\\") and not line.startswith("+++") and not line.startswith("---"):
                        current_line_number += 1
                
                # Only add to detailed changes if we found actual changes
                if lines_added or lines_removed:
                    detailed_changes.append({
                        "filename": file_path,
                        "status": file_status,
                        "change_type": change_type,
                        "lines_added": lines_added,
                        "lines_removed": lines_removed
                    })
        
        return {
            "success": True,
            "filename": file_path,
            "file_status": file_status,
            "index_status": index_status,
            "worktree_status": worktree_status,
            "detailed_changes": detailed_changes
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Git command failed: {e.stderr}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error: {str(e)}"
        }

@app.tool("get_commit_history")
async def get_commit_history(repo_url: Optional[str] = None, count: int = 10, branch: Optional[str] = None) -> Dict[str, Any]:
    """
    Get a list of all commits in the git repository or from a remote repository.
    
    This tool fetches the commit history, showing commit messages, authors, dates, and hashes.
    It can be used to view recent commits for the current repository or any GitHub repository.
    
    Args:
        repo_url: Optional URL of the repository to fetch history from. If not provided, uses the local repository.
        count: Number of commits to retrieve (default: 10)
        branch: Branch to get history from. If not provided, uses the current branch.
    
    Returns:
        Dictionary containing the commit history with details for each commit
    """
    try:
        if repo_url:
            # For remote repositories, create a temporary directory and clone
            import tempfile
            import shutil
            
            temp_dir = tempfile.mkdtemp()
            try:
                # Clone the repository to the temporary directory
                clone_cmd = ["git", "clone", "--depth", str(count + 5), repo_url, temp_dir]
                if branch:
                    clone_cmd.extend(["--branch", branch])
                
                clone_result = subprocess.run(
                    clone_cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if clone_result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Failed to clone repository: {clone_result.stderr}"
                    }
                
                # Change to the temporary directory for subsequent commands
                original_dir = os.getcwd()
                os.chdir(temp_dir)
                
                # Get the commit history
                result = _get_commit_history_internal(count, branch)
                
                # Change back to the original directory
                os.chdir(original_dir)
                
                # Clean up the temporary directory
                shutil.rmtree(temp_dir)
                
                return result
            except Exception as e:
                # Make sure we clean up the temporary directory
                shutil.rmtree(temp_dir)
                raise e
        else:
            # For local repository
            return _get_commit_history_internal(count, branch)
            
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Git command failed: {e.stderr}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error: {str(e)}"
        }

def _get_commit_history_internal(count: int, branch: Optional[str] = None) -> Dict[str, Any]:
    """
    Internal helper function to get commit history.
    
    Args:
        count: Number of commits to retrieve
        branch: Branch to get history from
    
    Returns:
        Dictionary containing the commit history
    """
    # Make sure we're in a git repository
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode != 0 or result.stdout.strip() != "true":
        return {
            "success": False,
            "error": "Not inside a git repository"
        }
    
    # Construct the git log command
    log_cmd = [
        "git", "log", 
        f"-{count}", 
        "--pretty=format:%H|%an|%ae|%ad|%s",
        "--date=iso"
    ]
    
    if branch:
        log_cmd.append(branch)
    
    # Run the git log command
    log_result = subprocess.run(
        log_cmd,
        capture_output=True,
        text=True,
        check=False
    )
    
    if log_result.returncode != 0:
        return {
            "success": False,
            "error": f"Git log command failed: {log_result.stderr}"
        }
    
    # Parse the log output
    commits = []
    for line in log_result.stdout.strip().split("\n"):
        if not line:
            continue
            
        parts = line.split("|")
        if len(parts) >= 5:
            commit = {
                "hash": parts[0],
                "author_name": parts[1],
                "author_email": parts[2],
                "date": parts[3],
                "message": parts[4]
            }
            commits.append(commit)
    
    # Get the current branch
    branch_cmd = ["git", "branch", "--show-current"]
    branch_result = subprocess.run(
        branch_cmd,
        capture_output=True,
        text=True,
        check=False
    )
    
    current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
    
    return {
        "success": True,
        "branch": current_branch,
        "commit_count": len(commits),
        "commits": commits
    }

def main():
    app.run()

if __name__ == "__main__":
    main()
