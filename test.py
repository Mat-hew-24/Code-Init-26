#!/usr/bin/env python3
"""
Test script for Grid-X mesh functionality
"""
import asyncio
import requests
import time
from discovery import start_mesh_node

async def test_mesh_discovery():
    """Test basic mesh discovery functionality"""
    print("🔍 Testing mesh discovery...")
    
    try:
        # Start a test node
        node = await start_mesh_node(port=8471)
        print("✅ Mesh node started successfully")
        
        # Wait for initialization
        await asyncio.sleep(2)
        
        # Test storing and retrieving data
        test_key = "test_node_data"
        test_value = "Status:Testing,Port:8000"
        
        await node.set(test_key, test_value)
        print("✅ Data stored in DHT")
        
        retrieved = await node.get(test_key)
        if retrieved == test_value:
            print("✅ Data retrieved successfully from DHT")
        else:
            print("❌ Data retrieval failed")
            
        return True
    except Exception as e:
        print(f"❌ Mesh discovery test failed: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints"""
    print("🌐 Testing API endpoints...")
    
    base_url = "http://localhost:8000"
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print("❌ Health endpoint failed")
            return False
            
        # Test status endpoint
        response = requests.get(f"{base_url}/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status endpoint working - Node is {data.get('status', 'Unknown')}")
        else:
            print("❌ Status endpoint failed")
            return False
            
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure a node is running on port 8000")
        return False
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def test_job_submission():
    """Test job submission"""
    print("🚀 Testing job submission...")
    
    base_url = "http://localhost:8000"
    
    try:
        # Simple test job
        job_data = {
            "image": "python:3.9-slim",
            "command": "python -c 'print(\"Grid-X test successful!\"); import sys; print(f\"Python version: {sys.version}\")'",
            "timeout": 30
        }
        
        print("Submitting test job...")
        response = requests.post(f"{base_url}/job", json=job_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Job executed successfully!")
            print(f"Exit code: {result.get('exit_code')}")
            print(f"Output:\n{result.get('logs')}")
            return True
        else:
            print(f"❌ Job submission failed: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure a node is running on port 8000")
        return False
    except Exception as e:
        print(f"❌ Job submission test failed: {e}")
        return False

async def main():
    print("=" * 50)
    print("         Grid-X System Test")
    print("=" * 50)
    
    # Test 1: Mesh Discovery
    mesh_ok = await test_mesh_discovery()
    print()
    
    # Test 2: API Endpoints
    api_ok = test_api_endpoints()
    print()
    
    # Test 3: Job Submission
    job_ok = test_job_submission()
    print()
    
    # Summary
    print("=" * 50)
    print("         Test Summary")
    print("=" * 50)
    print(f"Mesh Discovery: {'✅ PASS' if mesh_ok else '❌ FAIL'}")
    print(f"API Endpoints:  {'✅ PASS' if api_ok else '❌ FAIL'}")
    print(f"Job Submission: {'✅ PASS' if job_ok else '❌ FAIL'}")
    
    if mesh_ok and api_ok and job_ok:
        print("\n🎉 All tests passed! Grid-X is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the issues above.")
        print("\nTroubleshooting tips:")
        print("- Make sure Docker is running")
        print("- Make sure a Grid-X node is running (python main.py)")
        print("- Make sure no firewall is blocking ports 8000 or 8468")

if __name__ == "__main__":
    asyncio.run(main())