#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
import sys
import subprocess
import json
import os

def main():
    cwd = os.getcwd()
    testScript = os.path.join(cwd, sys.argv[1])
    inputOutputJsonPath = sys.argv[2]
    output = b''
    with open(inputOutputJsonPath, 'r') as f:
        inputOut = json.load(f)
    try:
        output = subprocess.check_output([testScript, inputOut['input']])
    except Exception as e:
        print("Program failed with exception: ")
        print(e)
        sys.exit()
    
    program_output = output.decode("utf-8")
    expected_output = inputOut['output']
    if (program_output == expected_output):
        print('success')
    else:
        print("expected:\n" + expected_output + "\n\nbut got:\n" + program_output)

if __name__ == "__main__":
    main()

