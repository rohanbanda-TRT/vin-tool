import requests
import json
import sys
import argparse

def get_changed_files():
    """Get a list of all changed files in the git repository."""
    response = requests.post(
        "http://localhost:8000/tools/get_changed_files",
        json={}
    )
    return response.json()

def get_file_diff(file_path, diff_type="all"):
    """Get the detailed diff for a specific file."""
    response = requests.post(
        "http://localhost:8000/tools/get_file_diff",
        json={
            "file_path": file_path,
            "diff_type": diff_type
        }
    )
    return response.json()

def get_commit_history(repo_url=None, count=10, branch=None):
    """Get the commit history for a git repository."""
    response = requests.post(
        "http://localhost:8000/tools/get_commit_history",
        json={
            "repo_url": repo_url,
            "count": count,
            "branch": branch
        }
    )
    return response.json()

def display_commit_history(commits):
    """Display commit history in a formatted way."""
    for i, commit in enumerate(commits, 1):
        hash_short = commit['hash'][:7]
        print(f"{i}. [{hash_short}] {commit['date']} - {commit['author_name']}")
        print(f"   {commit['message']}")
        print()

def main():
    parser = argparse.ArgumentParser(description="Git repository tools")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show repository status and changed files")
    
    # Diff command
    diff_parser = subparsers.add_parser("diff", help="Show diff for a specific file")
    diff_parser.add_argument("file_path", help="Path to the file to check")
    diff_parser.add_argument("--type", choices=["all", "staged", "unstaged"], default="all", 
                            help="Type of diff to get (all, staged, unstaged)")
    
    # History command
    history_parser = subparsers.add_parser("history", help="Show commit history")
    history_parser.add_argument("--repo", help="Repository URL (for remote repositories)")
    history_parser.add_argument("--count", type=int, default=10, help="Number of commits to show")
    history_parser.add_argument("--branch", help="Branch to get history from")
    
    args = parser.parse_args()
    
    if args.command == "history" or (len(sys.argv) > 1 and sys.argv[1] == "history"):
        # Handle commit history command
        if args.command == "history":
            repo_url = args.repo
            count = args.count
            branch = args.branch
        else:
            # Legacy command-line parsing for backward compatibility
            repo_url = None
            count = 10
            branch = None
            
            # Parse additional arguments
            for i in range(2, len(sys.argv)):
                arg = sys.argv[i]
                if arg.startswith("--repo="):
                    repo_url = arg.split("=", 1)[1]
                elif arg.startswith("--count="):
                    try:
                        count = int(arg.split("=", 1)[1])
                    except ValueError:
                        print(f"Invalid count value: {arg}")
                        return
                elif arg.startswith("--branch="):
                    branch = arg.split("=", 1)[1]
        
        print(f"Getting commit history{' for ' + repo_url if repo_url else ''}...")
        history_result = get_commit_history(repo_url, count, branch)
        
        if not history_result.get("success", False):
            print(f"Error: {history_result.get('error', 'Unknown error')}")
            return
        
        # Print repository information
        print(f"\nRepository Commit History:")
        if repo_url:
            print(f"Repository: {repo_url}")
        print(f"Branch: {history_result.get('branch', 'unknown')}")
        print(f"Found {history_result.get('commit_count', 0)} commits:")
        print()
        
        # Display commits
        display_commit_history(history_result.get("commits", []))
        return
    
    elif args.command == "diff":
        # Handle diff command
        file_to_check = args.file_path
        diff_type = args.type
        
        # Get and display diff for the selected file
        print(f"\nGetting diff for {file_to_check}...")
        diff_result = get_file_diff(file_to_check, diff_type)
        
        if not diff_result.get("success", False):
            print(f"Error: {diff_result.get('error', 'Unknown error')}")
            return
        
        # Print file status
        print(f"\nFile: {diff_result.get('filename')}")
        print(f"Status: {diff_result.get('file_status')}")
        
        # Print detailed changes
        detailed_changes = diff_result.get("detailed_changes", [])
        if not detailed_changes:
            print("No detailed changes found.")
            return
        
        for change in detailed_changes:
            change_type = change.get("change_type", "unknown")
            print(f"\n--- {change_type.upper()} CHANGES ---")
            
            # Print removed lines
            if change.get("lines_removed"):
                print("\nLines removed:")
                for line in change["lines_removed"]:
                    print(f"- {line['content']}")
            
            # Print added lines
            if change.get("lines_added"):
                print("\nLines added:")
                for line in change["lines_added"]:
                    print(f"+ [{line['line_number']}] {line['content']}")
        return
    
    elif args.command == "status" or not args.command:
        # First, get all changed files
        print("Getting list of changed files...")
        changed_files_result = get_changed_files()
        
        if not changed_files_result.get("success", False):
            print(f"Error: {changed_files_result.get('error', 'Unknown error')}")
            return
        
        # Print repository summary
        print(f"\nRepository Status:")
        print(f"Branch: {changed_files_result.get('branch', 'unknown')}")
        if "repo_summary" in changed_files_result:
            print(f"Summary: {changed_files_result['repo_summary']}")
        
        # Print changed files
        changed_files = changed_files_result.get("changed_files", [])
        if not changed_files:
            print("\nNo changes detected in the repository.")
            return
        
        print(f"\nFound {len(changed_files)} changed files:")
        for i, file_info in enumerate(changed_files, 1):
            status = file_info.get("status", "unknown")
            filename = file_info.get("filename", "unknown")
            print(f"{i}. [{status}] {filename}")
        
        # If no command was specified, show interactive menu
        if not args.command:
            print("\nOptions:")
            print("1. View file diff")
            print("2. View commit history")
            
            choice = input("Enter option number (or press Enter to exit): ")
            if not choice:
                return
                
            if choice == "1":
                try:
                    file_choice = input("Enter file number to see diff: ")
                    if not file_choice:
                        return
                    
                    file_index = int(file_choice) - 1
                    if file_index < 0 or file_index >= len(changed_files):
                        print("Invalid file number.")
                        return
                    
                    file_to_check = changed_files[file_index]["filename"]
                    diff_type = input("Enter diff type (all, staged, unstaged) [default: all]: ").strip() or "all"
                    
                    # Get and display diff for the selected file
                    print(f"\nGetting diff for {file_to_check}...")
                    diff_result = get_file_diff(file_to_check, diff_type)
                    
                    if not diff_result.get("success", False):
                        print(f"Error: {diff_result.get('error', 'Unknown error')}")
                        return
                    
                    # Print file status
                    print(f"\nFile: {diff_result.get('filename')}")
                    print(f"Status: {diff_result.get('file_status')}")
                    
                    # Print detailed changes
                    detailed_changes = diff_result.get("detailed_changes", [])
                    if not detailed_changes:
                        print("No detailed changes found.")
                        return
                    
                    for change in detailed_changes:
                        change_type = change.get("change_type", "unknown")
                        print(f"\n--- {change_type.upper()} CHANGES ---")
                        
                        # Print removed lines
                        if change.get("lines_removed"):
                            print("\nLines removed:")
                            for line in change["lines_removed"]:
                                print(f"- {line['content']}")
                        
                        # Print added lines
                        if change.get("lines_added"):
                            print("\nLines added:")
                            for line in change["lines_added"]:
                                print(f"+ [{line['line_number']}] {line['content']}")
                                
                except (ValueError, IndexError):
                    print("Invalid input.")
                    return
            elif choice == "2":
                repo_url = input("Enter repository URL (leave empty for local repository): ").strip() or None
                count_str = input("Enter number of commits to show [default: 10]: ").strip() or "10"
                try:
                    count = int(count_str)
                except ValueError:
                    print("Invalid count, using default (10).")
                    count = 10
                    
                branch = input("Enter branch name (leave empty for current branch): ").strip() or None
                
                # Get and display commit history
                print(f"\nGetting commit history{' for ' + repo_url if repo_url else ''}...")
                history_result = get_commit_history(repo_url, count, branch)
                
                if not history_result.get("success", False):
                    print(f"Error: {history_result.get('error', 'Unknown error')}")
                    return
                
                # Print repository information
                print(f"\nRepository Commit History:")
                if repo_url:
                    print(f"Repository: {repo_url}")
                print(f"Branch: {history_result.get('branch', 'unknown')}")
                print(f"Found {history_result.get('commit_count', 0)} commits:")
                print()
                
                # Display commits
                display_commit_history(history_result.get("commits", []))
            else:
                print("Invalid option.")
                return

if __name__ == "__main__":
    main()
