#!/usr/bin/env python3
"""Ingest documents into the knowledge base.

Usage examples:
    # Ingest a project directory
    python ingest.py --dir ./documents/my_project --collection my_project

    # Re-ingest (clear old data first)
    python ingest.py --dir ./documents/my_project --collection my_project --clear

    # List existing collections
    python ingest.py --list
"""

import argparse
import sys

from knowledge_base import KnowledgeBase


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into knowledge base")
    parser.add_argument("--dir", help="Directory with documents (.md, .txt, .rst)")
    parser.add_argument("--collection", help="Collection name (project / topic)")
    parser.add_argument("--clear", action="store_true", help="Clear collection before ingesting")
    parser.add_argument("--list", action="store_true", help="List existing collections")
    parser.add_argument("--delete", metavar="NAME", help="Delete a collection")
    args = parser.parse_args()

    kb = KnowledgeBase()

    if args.list:
        collections = kb.list_collections()
        if collections:
            print("Collections:")
            for name in collections:
                count = kb.collection_count(name)
                print(f"  - {name}  ({count} chunks)")
        else:
            print("No collections yet.")
        return

    if args.delete:
        kb.delete_collection(args.delete)
        print(f"Deleted: {args.delete}")
        return

    if not args.dir or not args.collection:
        parser.print_help()
        sys.exit(1)

    if args.clear:
        try:
            kb.delete_collection(args.collection)
            print(f"Cleared collection: {args.collection}")
        except Exception:
            pass

    print(f"Ingesting from {args.dir} -> collection '{args.collection}' ...")
    count = kb.ingest_directory(args.dir, args.collection)
    print(f"Done. {count} chunks indexed.")
    print(f"Available collections: {kb.list_collections()}")


if __name__ == "__main__":
    main()
