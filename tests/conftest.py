import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Ensure the backend package is importable from the project root
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
if os.path.isdir(backend_path) and backend_path not in sys.path:
    sys.path.insert(0, backend_path)
