#!/usr/bin/env python3
"""
Grid-X Launcher - All-in-one script to run Grid-X nodes and clients
"""
import os
import sys
import subprocess
import time
import requests
import asyncio
from pathlib import Path

def run_command(command, check=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=check)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr

def check_docker():
    """Check if Docker is installed and running"""
    print("🐳 Checking Docker...")
    success, _, _ = run_command("docker --version", check=False)
    if not success:
        print("❌ Docker is not installed!")
        print("   Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/")
        return False
    
    success, _, _ = run_command("docker info", check=False)
    if not success:
        print("❌ Docker is not running!")
        print("   Please start Docker Desktop and try again")
        return False
    
    print("✅ Docker is running")
    return True

def check_python():
    """Check Python version"""
    print(f"🐍 Python version: {sys.version}")
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required!")
        return False
    print("✅ Python version OK")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("📦 Installing Python dependencies...")
    success, _, _ = run_command("pip install docker fastapi uvicorn psutil kademlia requests pydantic jupyter nbformat nbconvert")
    if success:
        print("✅ Dependencies installed")
        return True
    else:
        print("❌ Failed to install dependencies")
        return False

def pull_docker_images():
    """Pull required Docker images"""
    print("📥 Pulling Docker images...")
    images = [
        "python:3.9-slim", 
        "alpine:latest",
        "jupyter/base-notebook:latest",
        "jupyter/datascience-notebook:latest"
    ]
    
    for image in images:
        print(f"   Pulling {image}...")
        success, _, _ = run_command(f"docker pull {image}")
        if not success:
            print(f"❌ Failed to pull {image}")
            return False
    
    print("✅ Docker images ready")
    return True

def setup_environment():
    """Complete setup process"""
    print("=" * 60)
    print("                    Grid-X Setup")
    print("=" * 60)
    
    if not check_python():
        return False
    
    if not check_docker():
        return False
    
    if not install_dependencies():
        return False
    
    if not pull_docker_images():
        return False
    
    print("\n🎉 Setup complete! Grid-X is ready to run.")
    return True

def start_node():
    """Start a Grid-X node"""
    print("🚀 Starting Grid-X Node...")
    print("   The node will start on http://localhost:8000")
    print("   Press Ctrl+C to stop the node")
    print()
    
    try:
        # Import and run the main node
        sys.path.append(os.getcwd())
        from main import start_all
        asyncio.run(start_all())
    except KeyboardInterrupt:
        print("\n⏹️  Grid-X node stopped")
    except Exception as e:
        print(f"\n❌ Error starting node: {e}")

def test_node():
    """Test if a node is running"""
    try:
        response = requests.get("http://localhost:8000/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Node is running - Status: {data.get('status', 'Unknown')}")
            return True
    except:
        pass
    
    print("❌ No node detected on localhost:8000")
    return False

def submit_test_job():
    """Submit a test job to demonstrate the system"""
    print("🧪 Submitting test job...")
    
    try:
        job_data = {
            "image": "python:3.9-slim",
            "command": "python -c 'print(\"🎉 Grid-X computation successful!\"); import platform; print(f\"Platform: {platform.system()}\"); print(f\"Python: {platform.python_version()}\")'",
            "timeout": 30
        }
        
        response = requests.post("http://localhost:8000/job", json=job_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print("\n" + "="*50)
            print("              JOB RESULTS")
            print("="*50)
            print(f"Status: {result.get('status', 'Unknown')}")
            print(f"Exit Code: {result.get('exit_code', 'Unknown')}")
            print("\nOutput:")
            print(result.get('logs', 'No output'))
            print("="*50)
            return True
        else:
            print(f"❌ Job failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error submitting job: {e}")
        return False

async def run_client():
    """Run the Grid-X client to find and submit jobs"""
    print("📤 Starting Grid-X Client...")
    print("   Searching for available Grid-X nodes...")
    
    try:
        sys.path.append(os.getcwd())
        from client import find_and_run_job
        
        # Test job - a simple computation
        job_image = "python:3.9-slim"
        job_cmd = (
            "python -c \""
            "print('🌟 Hello from Grid-X mesh network!'); "
            "import math, time; "
            "print(f'Computing π = {math.pi:.8f}'); "
            "print(f'Computing e = {math.e:.8f}'); "
            "print(f'Computing 1+1 = {1+1}'); "
            "print('Computation completed at', time.strftime('%H:%M:%S'));\""
        )
        
        await find_and_run_job(job_image, job_cmd)
        
    except KeyboardInterrupt:
        print("\\n⏹️ Client stopped by user")
    except Exception as e:
        print(f"❌ Client error: {e}")
        print("\\nTroubleshooting tips:")
        print("• Make sure Docker is running")
        print("• Start a Grid-X node first: python launcher.py")
        print("• Check if ports 8000-8002 are available")

async def run_notebook_client():
    """Run the Grid-X client for Jupyter notebooks"""
    print("📔 Starting Jupyter Notebook Client...")
    print("   Searching for .ipynb files in current directory...")
    
    try:
        import glob
        import base64
        import json
        
        # Find .ipynb files in current directory
        notebook_files = glob.glob("*.ipynb")
        
        if not notebook_files:
            print("❌ No .ipynb files found in current directory")
            print("   Please create or copy a Jupyter notebook file here first")
            return
        
        print(f"📄 Found {len(notebook_files)} notebook(s):")
        for i, file in enumerate(notebook_files, 1):
            print(f"   {i}. {file}")
        
        # Let user choose a notebook
        if len(notebook_files) == 1:
            chosen_file = notebook_files[0]
            print(f"📝 Automatically selected: {chosen_file}")
        else:
            while True:
                try:
                    choice = int(input(f"Choose notebook (1-{len(notebook_files)}): "))
                    if 1 <= choice <= len(notebook_files):
                        chosen_file = notebook_files[choice - 1]
                        break
                    else:
                        print("❌ Invalid choice")
                except ValueError:
                    print("❌ Please enter a number")

        # Read and encode the notebook
        print(f"📖 Reading {chosen_file}...")
        with open(chosen_file, 'r', encoding='utf-8') as f:
            notebook_content = f.read()
        
        # Validate it's a valid JSON notebook
        try:
            notebook_json = json.loads(notebook_content)
            if 'cells' not in notebook_json:
                print("❌ Invalid notebook format - no cells found")
                return
        except json.JSONDecodeError:
            print("❌ Invalid notebook format - not valid JSON")
            return
        
        # Use notebook client to submit job
        sys.path.append(os.getcwd())
        from client import find_and_run_notebook
        
        await find_and_run_notebook(chosen_file, notebook_content)
        
    except KeyboardInterrupt:
        print("\n⏹️ Notebook client stopped by user")
    except FileNotFoundError:
        print("❌ Selected notebook file not found")
    except Exception as e:
        print(f"❌ Notebook client error: {e}")
        print("\nTroubleshooting tips:")
        print("• Make sure the notebook file is valid JSON")
        print("• Make sure a Grid-X node is running")
        print("• Make sure Docker is running")

def main_menu():
    """Display main menu and handle user choices"""
    while True:
        print("\n" + "="*60)
        print("                     Grid-X Launcher")
        print("="*60)
        print("1. 🔧 Setup Grid-X (first time)")
        print("2. 🚀 Start Grid-X Node") 
        print("3. 📤 Run Grid-X Client")
        print("4. 📔 Run Jupyter Notebook")
        print("5. 🧪 Test Local Node")
        print("6. 📋 Quick Demo")
        print("7. ❌ Exit")
        print("="*60)
        
        choice = input("Choose an option (1-7): ").strip()
        
        if choice == "1":
            setup_environment()
        
        elif choice == "2":
            start_node()
        
        elif choice == "3":
            print("📤 Running client (make sure node is running first)...")
            asyncio.run(run_client())
        
        elif choice == "4":
            print("📔 Running Jupyter notebook executor...")
            asyncio.run(run_notebook_client())
        
        elif choice == "5":
            if test_node():
                submit_test_job()
        
        elif choice == "6":
            print("🎬 Quick Demo - This will test the entire system")
            print("   First testing if a node is running...")
            if test_node():
                submit_test_job()
            else:
                print("   No node running, starting one for demo...")
                print("   Open another terminal and run this script again with option 6")
        
        elif choice == "7":
            print("👋 Goodbye!")
            sys.exit(0)
        
        else:
            print("❌ Invalid choice, please try again")

if __name__ == "__main__":
    # If script is run with command line arguments, handle them
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "setup":
            setup_environment()
        elif arg == "node":
            start_node()
        elif arg == "client":
            asyncio.run(run_client())
        elif arg == "notebook":
            asyncio.run(run_notebook_client())
        elif arg == "test":
            if test_node():
                submit_test_job()
        else:
            print("Usage: python launcher.py [setup|node|client|notebook|test]")
    else:
        # Interactive mode
        main_menu()