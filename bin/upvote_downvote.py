import sys
import argparse
import json
from rag_tool import rag_record_user_feedback

def main():
    parser = argparse.ArgumentParser(description="Record user feedback")
    parser.add_argument("task_description", help="Task description")
    parser.add_argument("solution", help="Solution")
    parser.add_argument("vote", help="Upvote or downvote")
    parser.add_argument("--task_type", help="Task type", default=None)
    parser.add_argument("--context", help="Additional context", default=None)
    args = parser.parse_args()

    if len(args) < 4:
        print("用法: python upvote_downvote.py <task_description> <solution> <upvote|downvote> [task_type] [additional_context]")
        sys.exit(1)

    task_description = args.task_description
    solution = args.solution
    vote = args.vote
    task_type = args.task_type if args.task_type else None
    context = args.context if args.context else None
    result = rag_record_user_feedback(task_description, solution, vote, task_type, context)
    print(result)

if __name__ == "__main__":
    main()