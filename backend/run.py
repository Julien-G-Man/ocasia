#!/usr/bin/env python
"""
Django ASGI Server Runner

This script runs Django using Uvicorn ASGI server for async support.
Usage: python run_django.py [--port 8000] [--reload]

Default: runs on http://localhost:8000 with reload enabled
"""
import os
import sys
import argparse
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


def main():
    parser = argparse.ArgumentParser(
        description='Run Django with Uvicorn ASGI server'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port to run on (default: 8000)'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--reload',
        action='store_true',
        default=True,
        help='Enable auto-reload on code changes (default: True)'
    )
    parser.add_argument(
        '--no-reload',
        action='store_true',
        help='Disable auto-reload'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Number of worker processes (default: 1 for dev, use 4+ for production)'
    )

    args = parser.parse_args()
    
    # If --no-reload is specified, disable reload
    reload = args.reload and not args.no_reload
    
    # Import uvicorn here so we get a better error message if it's not installed
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed.")
        print("Install it with: pip install uvicorn[standard]")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("Django ASGI Server (Uvicorn)")
    print("="*60)
    print(f"Starting on http://{args.host}:{args.port}")
    print(f"Auto-reload: {'Enabled' if reload else 'Disabled'}")
    print(f"Workers: {args.workers}")
    print("="*60 + "\n")
    
    # Run uvicorn
    uvicorn.run(
        'config.asgi:application',
        host=args.host,
        port=args.port,
        reload=reload,
        workers=args.workers if not reload else 1,  # Single worker in reload mode
        loop='auto',
        log_level='info',
    )


if __name__ == '__main__':
    main()
