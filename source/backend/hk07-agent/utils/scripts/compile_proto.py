import os
import sys
import zipfile
import urllib.request
import subprocess

def download_protoc(dest_dir):
    """
    Downloads official protoc windows binary from GitHub.
    """
    protoc_version = "25.3"
    url = f"https://github.com/protocolbuffers/protobuf/releases/download/v{protoc_version}/protoc-{protoc_version}-win64.zip"
    zip_path = os.path.join(dest_dir, "protoc.zip")
    protoc_exe = os.path.join(dest_dir, "bin", "protoc.exe")
    
    if os.path.exists(protoc_exe):
        return protoc_exe
        
    print(f"Downloading protoc v{protoc_version} from {url}...")
    try:
        urllib.request.urlretrieve(url, zip_path)
        print("Extracting protoc...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return protoc_exe
    except Exception as e:
        print(f"Failed to download protoc: {e}")
        return None

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    agent_dir = os.path.dirname(script_dir)
    proto_dir = os.path.join(agent_dir, "proto")
    utils_dir = os.path.join(agent_dir, "utils")
    
    # Create temp directory for downloading protoc
    temp_dir = os.path.join(agent_dir, "build", "protoc_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    protoc_exe = download_protoc(temp_dir)
    if not protoc_exe:
        print("Using fallback grpc_tools.protoc if available...")
        try:
            from grpc_tools import protoc
            protoc_exe = "grpc_tools"
        except ImportError:
            print("ERROR: No protoc available.")
            sys.exit(1)

    proto_file = os.path.join(proto_dir, "pose_skeleton.proto")
    
    # Compile for Python
    print(f"Compiling {proto_file} for Python...")
    if protoc_exe == "grpc_tools":
        from grpc_tools import protoc
        cmd = ["protoc", f"-I{proto_dir}", f"--python_out={utils_dir}", proto_file]
        exit_code = protoc.main(cmd)
    else:
        cmd = [protoc_exe, f"-I{proto_dir}", f"--python_out={utils_dir}", proto_file]
        exit_code = subprocess.call(cmd)
        
    if exit_code == 0:
        print("Python Protobuf compilation succeeded!")
    else:
        print(f"Python Protobuf compilation failed with exit code: {exit_code}")
        
    # Compile for Java
    java_dest = os.path.normpath(os.path.join(agent_dir, "..", "hk07-core", "src", "main", "java"))
    os.makedirs(java_dest, exist_ok=True)
    print(f"Compiling {proto_file} for Java to {java_dest}...")
    
    if protoc_exe == "grpc_tools":
        # Attempt standard protoc command via grpc_tools.protoc wrapper
        # We need to make sure we don't request grpc plugin
        from grpc_tools import protoc
        cmd_java = ["protoc", f"-I{proto_dir}", f"--java_out={java_dest}", proto_file]
        exit_code_java = protoc.main(cmd_java)
    else:
        cmd_java = [protoc_exe, f"-I{proto_dir}", f"--java_out={java_dest}", proto_file]
        exit_code_java = subprocess.call(cmd_java)
        
    if exit_code_java == 0:
        print("Java Protobuf compilation succeeded!")
    else:
        print(f"Java Protobuf compilation failed with exit code: {exit_code_java}")

if __name__ == "__main__":
    main()
