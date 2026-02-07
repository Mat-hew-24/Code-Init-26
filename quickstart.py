#!/usr/bin/env python3
"""
Grid-X Quick Start - Run this file and it handles everything!
"""
import os
import sys
import subprocess
import time
import requests
import threading
import signal

# Flag to control the node thread
node_running = True

def run_command(command):
    """Run a shell command"""
    try:
        subprocess.run(command, shell=True, check=True, capture_output=True)
        return True
    except:
        return False

def quick_setup():
    """Install everything needed"""
    print("🔧 Setting up Grid-X...")
    
    # Install dependencies
    print("   Installing Python packages...")
    if not run_command("pip install docker fastapi uvicorn psutil kademlia requests pydantic"):
        print("❌ Failed to install packages. Please run: pip install -r requirements.txt")
        return False
    
    # Pull Docker images
    print("   Pulling Docker images...")
    if not run_command("docker pull python:3.9-slim"):
        print("❌ Failed to pull Docker image. Is Docker running?")
        return False
    
    print("✅ Setup complete!")
    return True

def start_node_background():
    """Start the Grid-X node in background"""
    try:
        sys.path.append(os.getcwd())
        import asyncio
        from main import start_all
        
        print("🚀 Starting Grid-X node on http://localhost:8000")
        asyncio.run(start_all())
    except Exception as e:
        print(f"❌ Node error: {e}")

def wait_for_node():
    """Wait for the node to be ready"""
    print("⏳ Waiting for node to start...")
    for i in range(10):
        try:
            response = requests.get("http://localhost:8000/status", timeout=2)
            if response.status_code == 200:
                print("✅ Node is ready!")
                return True
        except:
            pass
        time.sleep(1)
        print(f"   Waiting... {i+1}/10")
    
    print("❌ Node didn't start properly")
    return False

def run_test_job():
    """Run a test computation"""
    print("\n🧪 Running test computation...")
    
    try:
        job_data = {
            "image": "python:3.9-slim",
            "command": "python -c 'print(\"🎉 Grid-X is working!\"); import math; print(f\"Computing: π = {math.pi:.6f}\"); print(f\"Computing: e = {math.e:.6f}\")'",
            "timeout": 30
        }
        
        response = requests.post("http://localhost:8000/job", json=job_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print("\n" + "="*50)
            print("🎯 COMPUTATION RESULT")
            print("="*50)
            print(result.get('logs', 'No output'))
            print("="*50)
            print("✅ Grid-X is working perfectly!")
            return True
        else:
            print(f"❌ Job failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    global node_running
    node_running = False
    print("\n👋 Shutting down Grid-X...")
    sys.exit(0)

def main():
    """Main function - does everything automatically"""
    print("=" * 60)
    print("                  GRID-X QUICK START")
    print("=" * 60)
    print("This will set up and test Grid-X automatically!")
    print("Press Ctrl+C anytime to stop.")
    print()
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Step 1: Setup
    if not quick_setup():
        return
    
    print()
    print("🚀 Starting Grid-X demo...")
    print("   This will:")
    print("   1. Start a Grid-X node")
    print("   2. Wait for it to be ready") 
    print("   3. Run a test computation")
    print("   4. Show you the results")
    print()
    
    input("Press Enter to continue...")
    
    # Step 2: Start node in background
    node_thread = threading.Thread(target=start_node_background, daemon=True)
    node_thread.start()
    
    # Step 3: Wait for node to be ready
    if not wait_for_node():
        return
    
    # Step 4: Run test job
    success = run_test_job()
    
    if success:
        print()
        print("🎉 SUCCESS! Grid-X is working!")
        print()
        print("What happened:")
        print("✅ Started a Grid-X node (mesh network peer)")
        print("✅ Node checked system resources (CPU, RAM)")
        print("✅ Submitted a Python computation job")
        print("✅ Job ran securely in a Docker container")
        print("✅ Results returned safely")
        print()
        print("Next steps:")
        print("• Run 'python launcher.py' for full menu")
        print("• Run 'python main.py' to start a permanent node")
        print("• Run 'python client.py' to submit jobs to mesh")
        print("• Check the README.md for full documentation")
    else:
        print("❌ Something went wrong. Check the errors above.")
    
    print()
    print("Press Ctrl+C to stop or close this window.")
    
    # Keep running until user stops
    try:
        while node_running:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()